import re
import os
lines = open('wordslist.txt', 'r+', encoding='utf-8').readlines()
outFile = open('wordslist2.txt', 'w+', encoding='utf-8')
heads=[]
tails=[]
for i in lines:
    Match = re.match( r'(.*)\t(.*)', i)
    heads.append(Match.group(1))
    tails.append(Match.group(2))

#print(heads)
#print(tails)
#print()
results=''
for index, t in enumerate(tails):
    explains=[]
    examples=[]
    if re.search(r'(（[1-9]）|[Ⅰ-Ⅹ])', t):
        print('hello')
        examples=re.split(r'((?:（[1-9]）|[Ⅰ-Ⅹ]).*?)<br>', t)
        for i in examples:
            if re.search(r'(（[1-9]）|[Ⅰ-Ⅹ])', i):
                examples.remove(i)
                explains.append(i)
        if '' in examples:
            examples.remove('')
    elif '<br>' in t:
        Match=re.match(r'(.*?)<br>(.*)', t)
        explains.append(Match.group(1))
        examples.append(Match.group(2))
    else:
        explains.append(t)

    tmpexp=[]
    for iii in examples:
        tmpexp.extend(iii.split('<br>'))
    examples = list(tmpexp)
    tmpexp.clear()
    for iii in examples:
        if not '／' in iii:
            tmpexp.append(iii)
            continue
        tmps=iii.split('／')
        tmps[0]='<b>'+tmps[0]+'</b><br>'
        tmps[1]='　'+tmps[1]+'<br>'
        tmpexp.extend(tmps)
    examples=tmpexp

    print(explains)
    print(examples)
    print()
    s=''
    for i in explains:
        s=s+i+'<br>'
    s=s+'\t'
    for ii in examples:
        s=s+ii
    s=s+'\n'
    outFile.write(heads[index]+'\t'+s)
outFile.close()
    
