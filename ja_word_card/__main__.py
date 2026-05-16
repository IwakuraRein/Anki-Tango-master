from __future__ import annotations

import configparser
import ctypes
import inspect
import os
import queue
import threading
import tkinter as tk
from collections.abc import Mapping
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from types import UnionType
from typing import Any, get_args, get_origin

from .output_formater import AnkiFormatter, JsonFormatter
from .query import BaseQuery, DictWord

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    ctypes.windll.user32.SetProcessDPIAware()


def default_icon_path() -> Path:
    return Path(__file__).resolve().parent.parent / "logo.ico"


def app_config_path() -> Path:
    appdata = os.getenv("APPDATA")
    base_path = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base_path / "ja_word_card" / "config.ini"


def parse_words(text: str) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()

    for line in text.splitlines():
        word = line.strip()
        if not word or word in seen:
            continue
        words.append(word)
        seen.add(word)

    return words


def discover_backends() -> dict[str, type[BaseQuery]]:
    return {
        backend.name: backend
        for backend in BaseQuery.__subclasses__()
        if getattr(backend, "name", None)
    }


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin not in (UnionType, getattr(__import__("typing"), "Union")):
        return annotation, False

    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if len(args) != len(get_args(annotation)):
        return (args[0] if args else str), True
    return annotation, False


def parameter_type(parameter: inspect.Parameter) -> tuple[type[Any], bool]:
    annotation = parameter.annotation
    optional = parameter.default is None

    if annotation is inspect.Parameter.empty:
        if parameter.default not in (inspect.Parameter.empty, None):
            return type(parameter.default), optional
        return str, optional

    annotation, annotation_optional = unwrap_optional(annotation)
    optional = optional or annotation_optional

    if annotation in (str, Path, int, float, bool):
        return annotation, optional

    return str, optional


def backend_config_section(backend_name: str) -> str:
    return f"backend.{backend_name}"


class WordCardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Japanese Word Card")
        self._set_window_icon()
        self.geometry("980x1024")
        self.minsize(640, 640)
        try:
            self.scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0)
        except:
            self.scale_factor = 1
        self.tk.call("tk", "scaling", self.scale_factor / 75)

        self.output_formatters = {
            JsonFormatter.name: JsonFormatter(),
            AnkiFormatter.name: AnkiFormatter(),
        }
        self.backends = discover_backends()
        self.backend_var = tk.StringVar(
            value="SQLite" if "SQLite" in self.backends else next(iter(self.backends))
        )
        self.output_format_var = tk.StringVar(value=next(iter(self.output_formatters)))
        self.backend_param_vars: dict[str, tk.Variable] = {}
        self.backend_param_types: dict[str, type[Any]] = {}
        self.backend_optional_params: set[str] = set()
        self.config_path = app_config_path()
        self.config = configparser.ConfigParser()
        self.loading_backend_params = False
        self.query_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.query_thread: threading.Thread | None = None
        self.status_var = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar(value=0)
        self._ensure_config_file()
        self.config.read(self.config_path, encoding="utf-8")

        self._build_widgets()
        self._build_backend_param_controls()

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=(12, 12, 12, 6))
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(4, weight=1)
        controls.columnconfigure(1, weight=0)
        controls.columnconfigure(3, weight=0)

        ttk.Label(controls, text="Backend").grid(row=0, column=0, sticky="w")
        backend_box = ttk.Combobox(
            controls,
            textvariable=self.backend_var,
            values=tuple(self.backends),
            state="readonly",
            width=12,
        )
        backend_box.grid(row=0, column=1, padx=(6, 16), sticky="w")
        backend_box.bind("<<ComboboxSelected>>", self._build_backend_param_controls)

        ttk.Label(controls, text="Output").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            controls,
            textvariable=self.output_format_var,
            values=tuple(self.output_formatters),
            state="readonly",
            width=12,
        ).grid(row=0, column=3, padx=(6, 16), sticky="w")

        self.query_button = ttk.Button(
            controls,
            text="Query",
            command=self._run_query,
        )
        self.query_button.grid(row=0, column=5, sticky="e")

        self.backend_params_frame = ttk.Frame(controls)
        self.backend_params_frame.grid(
            row=1,
            column=0,
            columnspan=6,
            pady=(8, 0),
            sticky="ew",
        )
        self.backend_params_frame.columnconfigure(1, weight=1)

        panes = ttk.PanedWindow(self, orient=tk.VERTICAL)
        panes.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 8))

        input_frame = ttk.LabelFrame(panes, text="Input words")
        output_frame = ttk.LabelFrame(panes, text="Found words")
        failed_frame = ttk.LabelFrame(panes, text="Not found")

        panes.add(input_frame, weight=1)
        panes.add(output_frame, weight=3)
        panes.add(failed_frame, weight=1)

        self.input_text = self._text_area(input_frame, height=7)
        self.output_text = self._text_area(output_frame, height=18)
        self.failed_text = self._text_area(failed_frame, height=7)

        progress_frame = ttk.Frame(self, padding=(12, 0, 12, 4))
        progress_frame.grid(row=2, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=1,
            mode="determinate",
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        status = ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padding=(12, 0, 12, 10),
        )
        status.grid(row=3, column=0, sticky="ew")

    def _set_window_icon(self) -> None:
        icon_path = default_icon_path()
        if not icon_path.is_file():
            return

        try:
            self.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

    def _text_area(self, parent: ttk.LabelFrame, height: int) -> tk.Text:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        text = tk.Text(parent, wrap="word", undo=True, height=height)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        return text

    def _build_backend_param_controls(self, event: tk.Event | None = None) -> None:
        self.loading_backend_params = True
        for child in self.backend_params_frame.winfo_children():
            child.destroy()

        self.backend_param_vars = {}
        self.backend_param_types = {}
        self.backend_optional_params = set()

        try:
            backend_class = self.backends.get(self.backend_var.get())
            if backend_class is None:
                return

            for row, parameter in enumerate(
                self._backend_init_parameters(backend_class)
            ):
                value_type, optional = parameter_type(parameter)
                self.backend_param_types[parameter.name] = value_type
                if optional:
                    self.backend_optional_params.add(parameter.name)

                ttk.Label(
                    self.backend_params_frame,
                    text=parameter.name,
                ).grid(row=row, column=0, sticky="w", pady=(0, 6))

                variable = self._create_param_variable(parameter, value_type)
                self.backend_param_vars[parameter.name] = variable
                self._trace_backend_param(parameter.name, variable)

                if value_type is bool:
                    ttk.Checkbutton(
                        self.backend_params_frame,
                        variable=variable,
                    ).grid(row=row, column=1, sticky="w", pady=(0, 6))
                    continue

                ttk.Entry(
                    self.backend_params_frame,
                    textvariable=variable,
                ).grid(row=row, column=1, sticky="ew", padx=(6, 6), pady=(0, 6))

                if value_type is Path:
                    ttk.Button(
                        self.backend_params_frame,
                        text="Browse",
                        command=lambda name=parameter.name: self._choose_path(name),
                    ).grid(row=row, column=2, sticky="e", pady=(0, 6))
        finally:
            self.loading_backend_params = False

    def _backend_init_parameters(
        self,
        backend_class: type[BaseQuery],
    ) -> list[inspect.Parameter]:
        signature = inspect.signature(backend_class.__init__, eval_str=True)
        return [
            parameter
            for parameter in signature.parameters.values()
            if parameter.name != "self"
            and parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]

    def _create_param_variable(
        self,
        parameter: inspect.Parameter,
        value_type: type[Any],
    ) -> tk.Variable:
        default = self._default_param_value(parameter, value_type)
        if value_type is bool:
            return tk.BooleanVar(value=bool(default))
        return tk.StringVar(value="" if default is None else str(default))

    def _default_param_value(
        self,
        parameter: inspect.Parameter,
        value_type: type[Any],
    ) -> object:
        config_value = self._configured_backend_value(parameter.name)
        if config_value is not None:
            return self._parse_config_value(config_value, value_type)
        if parameter.default is not inspect.Parameter.empty:
            return parameter.default
        return None

    def _configured_backend_value(self, parameter_name: str) -> str | None:
        section = backend_config_section(self.backend_var.get())
        if not self.config.has_option(section, parameter_name):
            return None
        return self.config.get(section, parameter_name)

    def _parse_config_value(self, value: str, value_type: type[Any]) -> object:
        if value_type is bool:
            return self.config.BOOLEAN_STATES.get(value.lower(), False)
        return value

    def _trace_backend_param(self, name: str, variable: tk.Variable) -> None:
        variable.trace_add("write", lambda *_: self._save_backend_argument(name))

    def _ensure_config_file(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.touch(exist_ok=True)
        except OSError as error:
            self.status_var.set(f"Could not create config: {error}")

    def _save_backend_argument(self, name: str) -> None:
        if self.loading_backend_params:
            return

        section = backend_config_section(self.backend_var.get())
        if not self.config.has_section(section):
            self.config.add_section(section)

        value = self.backend_param_vars[name].get()
        if self.backend_param_types.get(name) is bool:
            config_value = "true" if bool(value) else "false"
        else:
            config_value = str(value)

        self.config.set(section, name, config_value)
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open("w", encoding="utf-8") as config_file:
                self.config.write(config_file)
        except OSError as error:
            self.status_var.set(f"Could not save config: {error}")

    def _choose_path(self, parameter_name: str) -> None:
        variable = self.backend_param_vars[parameter_name]
        current_parent = Path(str(variable.get())).expanduser().parent
        initial_dir = current_parent if current_parent.exists() else Path.cwd()
        path = filedialog.askopenfilename(
            title=f"Choose {parameter_name}",
            filetypes=(
                ("SQLite databases", "*.sqlite *.sqlite3 *.db"),
                ("All files", "*.*"),
            ),
            initialdir=str(initial_dir),
        )
        if path:
            variable.set(path)

    def _run_query(self) -> None:
        if self._query_is_running():
            messagebox.showinfo("Query running", "A query is already running.")
            return

        words = parse_words(self.input_text.get("1.0", tk.END))
        if not words:
            messagebox.showinfo("No input", "Please enter at least one word.")
            return

        formatter = self.output_formatters.get(self.output_format_var.get())
        if formatter is None:
            messagebox.showerror("Unsupported output", "Unsupported output format.")
            return

        try:
            backend_class = self._selected_backend()
            backend_kwargs = self._backend_kwargs()
        except ValueError as error:
            messagebox.showerror("Backend parameters", str(error))
            return

        self._set_query_running(True)
        self._drain_query_queue()
        self._set_text(self.output_text, "")
        self._set_text(self.failed_text, "")
        self.progress_bar.configure(maximum=len(words))
        self.progress_var.set(0)
        self.status_var.set(f"Querying 0/{len(words)} word(s)...")

        self.query_thread = threading.Thread(
            target=self._query_worker,
            args=(backend_class, backend_kwargs, words),
            daemon=True,
        )
        self.query_thread.start()
        self.after(100, lambda: self._poll_query_queue(formatter, len(words)))

    def _selected_backend(self) -> type[BaseQuery]:
        backend_class = self.backends.get(self.backend_var.get())
        if backend_class is None:
            raise ValueError(f"Unsupported backend: {self.backend_var.get()}")
        return backend_class

    def _backend_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {}
        for name, variable in self.backend_param_vars.items():
            raw_value = variable.get()
            value_type = self.backend_param_types[name]
            kwargs[name] = self._convert_backend_value(name, raw_value, value_type)
        return kwargs

    def _convert_backend_value(
        self,
        name: str,
        value: object,
        value_type: type[Any],
    ) -> object:
        if value_type is bool:
            return bool(value)

        text = str(value).strip()
        if not text and name in self.backend_optional_params:
            return None
        if not text:
            raise ValueError(f"{name} is required.")

        if value_type is Path:
            return Path(text).expanduser()
        if value_type is int:
            return int(text)
        if value_type is float:
            return float(text)
        return text

    def _query_worker(
        self,
        backend_class: type[BaseQuery],
        backend_kwargs: Mapping[str, object],
        words: list[str],
    ) -> None:
        try:
            query = backend_class(**backend_kwargs)
            if not query.is_loaded():
                self.query_queue.put(
                    ("error", f"Could not load backend: {backend_class.name}")
                )
                return

            found: dict[str, DictWord] = {}
            failed: list[str] = []

            for done, word in enumerate(words, start=1):
                try:
                    found[word] = query.query(word)
                except Exception as e:
                    failed.append(word)
                    self.query_queue.put(
                        ("progress", (done, len(found), len(failed), str(e)))
                    )
                else:
                    self.query_queue.put(
                        ("progress", (done, len(found), len(failed), ""))
                    )

            self.query_queue.put(("done", (found, failed)))
        except Exception as error:
            self.query_queue.put(("error", str(error)))

    def _poll_query_queue(self, formatter: object, total: int) -> None:
        should_continue = self._query_is_running()

        while True:
            try:
                message, payload = self.query_queue.get_nowait()
            except queue.Empty:
                break

            if message == "progress":
                done, found_count, failed_count, extra_msg = payload
                self.progress_var.set(done)
                self.status_var.set(
                    "Querying "
                    f"{done}/{total} word(s). "
                    f"{found_count} found, {failed_count} failed. {extra_msg}"
                )
            elif message == "done":
                found, failed = payload
                self.progress_var.set(total)
                self._set_text(self.output_text, formatter.format_many(found))
                self._set_text(self.failed_text, "\n".join(failed))
                self.status_var.set(f"Done. {len(found)} found, {len(failed)} faild.")
                self._set_query_running(False)
                should_continue = False
            elif message == "error":
                self.status_var.set("Query failed.")
                messagebox.showerror("Query failed", str(payload))
                self._set_query_running(False)
                should_continue = False

        if should_continue:
            self.after(100, lambda: self._poll_query_queue(formatter, total))

    def _query_is_running(self) -> bool:
        return self.query_thread is not None and self.query_thread.is_alive()

    def _set_query_running(self, running: bool) -> None:
        self.query_button.configure(state="disabled" if running else "normal")
        if not running:
            self.query_thread = None

    def _drain_query_queue(self) -> None:
        while True:
            try:
                self.query_queue.get_nowait()
            except queue.Empty:
                return

    def _set_text(self, text: tk.Text, value: str) -> None:
        text.delete("1.0", tk.END)
        text.insert("1.0", value)


def main() -> None:
    app = WordCardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
