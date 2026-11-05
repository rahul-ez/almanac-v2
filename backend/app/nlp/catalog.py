"""Catalog acquisition is outside the pure interpreter; no model-generated SQL."""
import re
from app.nlp.text import normalized
from sqlalchemy import select
from app.api.errors import ApiError
from app.db.models import Department,Building,Topic,Event
from app.db.room_models import Room,Facility
from app.db.faculty_models import Faculty,FacultyAlias
from app.schemas.interpretation import CampusCatalog,CatalogEntry


def load_catalog(conn):
    entries=[]
    aliases={}
    for row in conn.execute(select(FacultyAlias.canonical_id,FacultyAlias.alias).where(FacultyAlias.status=='active').limit(20001)).mappings():
        aliases.setdefault(row['canonical_id'],[]).append(row['alias'])
    if sum(map(len,aliases.values()))>20000: raise ApiError(503,'catalog_limit','Campus alias catalog exceeds the configured bound')
    declared={'department':{'aiml':['AI & ML','AI and ML'],'cse':['CS','computer science']},
              'topic':{'machine_learning':['ML','machine learning'],'artificial_intelligence':['AI','artificial intelligence'],'web_development':['web development']},
              'facility':{'projector':['projectors'],'whiteboard':['whiteboards'],'computers':['computer','PCs']}}
    for kind,model in [('department',Department),('building',Building),('topic',Topic),('facility',Facility)]:
        rows=list(conn.execute(select(model.__table__).limit(20001)).mappings())
        if len(rows)>20000: raise ApiError(503,'catalog_limit','Campus catalog exceeds the configured bound')
        for row in rows:
            names=[row['id'],row['label'],row['id'].replace('_',' '),*declared.get(kind,{}).get(row['id'],[])]
            if kind=='building' and row['id'].startswith('block-'):
                block=row['id'][6:];names += [f'{block} block',f'block {block}']
            entries.append(CatalogEntry(kind=kind,id=row['id'],label=row['label'],aliases=names))
    for model,kind in [(Room,'room'),(Faculty,'faculty')]:
        rows=list(conn.execute(select(model.__table__).where(model.status=='active').limit(20001)).mappings())
        if len(rows)>20000: raise ApiError(503,'catalog_limit','Campus catalog exceeds the configured bound')
        for row in rows:
            if kind=='room':
                names=[row['code'],row['id']]
                if row['code'].startswith('DEMO-'):
                    import re
                    short=row['code'][5:];names += [short,re.sub(r'^([A-Za-z]+)(\d+)$',r'\1-\2',short)]
                entries.append(CatalogEntry(kind=kind,id=row['id'],label=row['code']+' · '+row['building_id'],aliases=names))
            else:
                names=[row['name'],row['normalized_name'],*aliases.get(row['id'],[])]
                if row['name'].startswith('[DEMO] '):
                    names.append(row['name'][7:])
                entries.append(CatalogEntry(kind=kind,id=row['id'],label=row['name']+' · '+row['department_id'],department_id=row['department_id'],
                    aliases=names))
    venues=list(conn.execute(select(Event.venue).where(Event.status=='published').distinct().limit(20001)).scalars())
    if len(venues)>20000: raise ApiError(503,'catalog_limit','Campus venue catalog exceeds the configured bound')
    entries += [CatalogEntry(kind='venue',id=venue,label=venue,aliases=[venue]) for venue in venues]
    # Vocabulary comes from published event titles, not a hardcoded list of sample questions.
    known={normalized(name) for entry in entries for name in [entry.label,*entry.aliases]}
    reserved=set('a an and any are as at be by can demo event events find for free from happening i in is it me next of on or please show the there this to today tomorrow upcoming what when which with workshop workshops seminar seminars lecture lectures hackathon hackathons room rooms faculty office hours week month year second first third fourth'.split())
    titles=list(conn.execute(select(Event.title).where(Event.status=='published').limit(20001)).scalars())
    if len(titles)>20000: raise ApiError(503,'catalog_limit','Published event catalog exceeds the configured bound')
    keywords={term for title in titles for term in re.findall(r"[\w]+(?:[-'][\w]+)*",normalized(title)) if 2<=len(term)<=100 and not term.isdigit() and term not in reserved and term not in known}
    entries += [CatalogEntry(kind='event_keyword',id=term,label=term,aliases=[term]) for term in sorted(keywords)]
    if len(entries)>20000: raise ApiError(503,'catalog_limit','Campus catalog exceeds the configured bound')
    return CampusCatalog(entries=entries)
