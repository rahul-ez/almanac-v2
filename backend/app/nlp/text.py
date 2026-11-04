"""Normalization with original-text offsets, including combining marks/case expansions."""
import unicodedata

class TextView:
    def __init__(self,text):
        self.original=text;self.text='';self.mapping=[]
        clusters=[]
        for index,char in enumerate(text):
            if clusters and unicodedata.combining(char):
                clusters[-1][1]+=char;clusters[-1][2]=index+1
            else: clusters.append([index,char,index+1])
        for start,cluster,end in clusters:
            for char in unicodedata.normalize('NFKC',cluster).casefold():
                if char.isspace():
                    if self.text.endswith(' '):
                        prior=self.mapping[-1];self.mapping[-1]=(prior[0],end)
                        continue
                    char=' '
                self.text+=char;self.mapping.append((start,end))
        self.used=[False]*len(self.text)

    def available(self):
        return ''.join(' ' if used else char for char,used in zip(self.text,self.used))

    def reserve(self,start,end):
        for index in range(start,end): self.used[index]=True

    def original_span(self,start,end):
        a,b=self.mapping[start][0],self.mapping[end-1][1]
        return a,b,self.original[a:b]


def normalized(text):
    return TextView(text).text.strip()
