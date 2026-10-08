"""Normalize the agreed CV heading and GMAS role while preserving other job titles."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def normalize_cv_identity(source, target, lang):
 source=Path(source);target=Path(target)
 with ZipFile(source) as archive:
  payloads={entry.filename:(entry,archive.read(entry.filename)) for entry in archive.infolist()}
 tree=etree.fromstring(payloads['word/document.xml'][1])
 changed=0
 for index,paragraph in enumerate(tree.iter(W+'p')):
  nodes=[]
  for node in paragraph.iter(W+'t'):
   owner=node.getparent()
   while owner is not None and owner.tag!=W+'p':owner=owner.getparent()
   if owner is paragraph:nodes.append(node)
  text=''.join(node.text or '' for node in nodes)
  replacement=None
  if index<8 and text.strip() in ('Геолог','Geologist'):
   replacement=('Ведущий геолог' if lang=='ru' else 'Senior Geologist')
  elif text.startswith('Геолог с '):replacement='Ведущий геолог'+text[len('Геолог'):]
  elif text.startswith('Geologist with '):replacement='Senior Geologist'+text[len('Geologist'):]
  elif text.strip()=='Руководитель полевой партии / Полевой геолог':replacement='Ведущий геолог партии'
  elif text.strip()=='Field team leader, field geologist':replacement='Senior Geologist, Field Party'

  if replacement is not None and nodes:
   old=text;prefix=0
   while prefix<min(len(old),len(replacement)) and old[prefix]==replacement[prefix]:prefix+=1
   suffix=0
   while suffix<min(len(old)-prefix,len(replacement)-prefix) and old[-suffix-1]==replacement[-suffix-1]:suffix+=1
   end=len(old)-suffix;insert=replacement[prefix:len(replacement)-suffix if suffix else len(replacement)]
   if end==prefix:
    cursor=0
    for node in nodes:
     original=node.text or ''
     if cursor<=prefix<=cursor+len(original):
      offset=prefix-cursor
      node.text=original[:offset]+insert+original[offset:]
      node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
      break
     cursor+=len(original)
    changed+=1
    continue
   cursor=0;inserted=False
   for node in nodes:
    original=node.text or '';start=cursor;finish=cursor+len(original);cursor=finish
    if finish<=prefix or start>=end:continue
    left=original[:max(0,prefix-start)]
    right=original[max(0,end-start):] if end<finish else ''
    node.text=left+(insert if not inserted else '')+right
    node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    inserted=True
   changed+=1
 payloads['word/document.xml']=(payloads['word/document.xml'][0],etree.tostring(tree,encoding='UTF-8',xml_declaration=True,standalone=True))
 staging=target.with_suffix('.normalized.docx')
 with ZipFile(staging,'w') as archive:
  for entry,payload in payloads.values():archive.writestr(entry,payload)
 staging.replace(target)
 return changed


if __name__=='__main__':
 import shutil
 root=Path(__file__).resolve().parents[1]
 backup=root/'.analysis/cv-review/originals';backup.mkdir(parents=True,exist_ok=True)
 for lang in ('ru','en'):
  target=root/f'public/cv/Aleksei-Pakhalko-CV-{lang.upper()}-2026.docx'
  if not (backup/target.name).exists():shutil.copy2(target,backup/target.name)
  print(lang,normalize_cv_identity(target,target,lang),'CV profile updates; leading engineer position preserved')
