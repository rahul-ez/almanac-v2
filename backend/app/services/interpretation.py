"""Acquire trusted context/catalog, then call the shared pure pipeline."""
from app.nlp.catalog import load_catalog
from app.nlp.pipeline import interpret_catalog
from app.repositories.profiles import read_profile


def interpret_question(conn,payload,user_id,now,campus_timezone,*,nlp_mode='baseline',intent_model=None,prior_meaning=None,selected_intent=None,now_minutes=30,horizon_days=30):
    profile=read_profile(conn,user_id)
    catalog=load_catalog(conn)
    report=interpret_catalog(payload.text,catalog=catalog,now=now,campus_timezone=campus_timezone,
        profile={'student_year':profile['year'],'department_id':profile['department_id']},
        overrides=payload.context_overrides.model_dump(exclude_unset=True),nlp_mode=nlp_mode,intent_model=intent_model,
        prior_meaning=prior_meaning,selected_intent=selected_intent,now_minutes=now_minutes,horizon_days=horizon_days)
    return report,catalog
