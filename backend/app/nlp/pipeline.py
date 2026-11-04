"""Shared pure rules/model boundary used by production and offline evaluation."""
from app.api.errors import ApiError
from app.nlp.interpreter import interpret,choose_intent,Problem
from app.nlp.text import TextView
from app.schemas.interpretation import Interpretation


def interpret_catalog(text,*,catalog,now,campus_timezone,profile=None,overrides=None,nlp_mode='baseline',intent_model=None,prior_meaning=None,selected_intent=None):
    if nlp_mode=='hybrid' and intent_model is None:
        raise ApiError(503,'model_unavailable','Configured intent model is unavailable or incompatible')
    selected=selected_intent;confidence=None;has_domain=False
    if prior_meaning is not None:
        try: choose_intent(TextView(text),[],None);has_domain=True
        except Problem: pass
    if nlp_mode=='hybrid' and (prior_meaning is None or has_domain) and selected_intent is None:
        selected,confidence=intent_model.predict(text)
        if selected=='unsupported':
            return Interpretation(status='unsupported',intent=None,meaning=None,execution=None,entities=[],applied_context=[],
                unsupported_constraints=['intent_rejected'],message='The intent model cannot confidently support this question. Rephrase a complete campus question.',
                intent_source='model',model_version=intent_model.version,intent_confidence=confidence)
    report=interpret(text,catalog=catalog,now=now,campus_timezone=campus_timezone,profile=profile,overrides=overrides,
        selected_intent=selected,prior_meaning=prior_meaning)
    if selected_intent is not None: report.intent_source='rules'
    if intent_model is not None and nlp_mode=='hybrid':
        report.model_version=intent_model.version;report.intent_confidence=confidence
    return report
