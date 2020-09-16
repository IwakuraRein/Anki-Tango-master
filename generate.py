import os
import re
from pykakasi import kakasi
Words = []


def WordOut(file, i):
    file.write(lines[i].lstrip('{').rstrip('\n')+'\t')
    while lines[i][0] != '}':
        i += 1
        if lines[i][0] != '\n' and lines[i][0] != '}':
            s = lines[i].replace('\n', '<br>')
            if re.match(r'发音：[a-z]*.*<br>',s):
                tmp=re.match(r'发音：[a-z]*(.*?)<br>',s).group(1)+'\t'
                s=re.sub(r'发音：[a-z]*.*<br>',tmp,s)
            file.write(s)
    file.write('\n')


kakasi = kakasi()
kakasi.setMode('a', 'H')
kakasi.setMode('K', 'H')
kakasi.setMode('J', 'H')
conv = kakasi.getConverter()

lines = open('JA-ZHdict.dat', 'r', encoding='utf-8').readlines()
index = open('JA-ZHdictindex.dat', 'r', encoding='utf-8').read().splitlines()
pronindex = open('JA-ZHdictpronindex.dat', 'r',
                 encoding='utf-8').read().splitlines()
print('请输入单词（输入\\END结束）：')
matches = list()
unMatches = list()
while True:
    tmp = input()
    if tmp == '\\END':
        break
    else:
        Words.append(tmp)
for num, i in enumerate(Words):
    print('\r{:3}%'.format(int(100*(num+1)/len(Words))), end='')
    try:
        location = index.index(i)
    except ValueError:
        try:
            location = pronindex.index(conv.do(i))
        except ValueError:
            unMatches.append(i)
        else:
            location += 1
            matches.append(eval(pronindex[location])-1)
    else:
        location += 1
        matches.append(eval(index[location]))

outFile = open('wordslist.txt', 'w+', encoding='utf-8')
for i in matches:
    WordOut(outFile, i)
outFile.close()
print('')
print('Done!')
if unMatches:
    print('以下单词没找到释义：')
    for i in unMatches:
        print(i)
    os.system('pause')
Path = os.path.join(os.getcwd(), 'wordslist.txt')
os.startfile(Path)
