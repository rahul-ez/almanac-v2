from sqlalchemy import select, update, insert, delete
from app.db.models import StudentProfile, ProfileInterest, Department, Topic
from app.api.errors import ApiError


def read_profile(conn, user_id):
    row = conn.execute(select(StudentProfile.__table__).where(StudentProfile.user_id == user_id)).mappings().first()
    if row is None:
        raise ApiError(404, "not_found", "Profile not found")
    interests = list(conn.execute(select(ProfileInterest.topic_id).where(ProfileInterest.user_id == user_id).order_by(ProfileInterest.topic_id)).scalars())
    return dict(row, interests=interests)


def patch_profile(conn, user_id, patch):
    row = conn.execute(select(StudentProfile.user_id).where(StudentProfile.user_id == user_id).with_for_update()).first()
    if row is None:
        raise ApiError(404, "not_found", "Profile not found")
    values = patch.model_dump(exclude_unset=True)
    department = values.get('department_id')
    if department is not None and conn.execute(select(Department.id).where(Department.id == department)).first() is None:
        raise ApiError(422, "validation_error", "Unknown department", [{'field': 'body.department_id', 'message': 'Choose a reference department'}])
    if 'interests' in values:
        topics = values.pop('interests')
        found = set(conn.execute(select(Topic.id).where(Topic.id.in_(topics))).scalars())
        if set(topics) != found:
            raise ApiError(422, "validation_error", "Unknown interest", [{'field': 'body.interests', 'message': 'Choose reference topics'}])
        conn.execute(delete(ProfileInterest).where(ProfileInterest.user_id == user_id))
        if topics:
            conn.execute(insert(ProfileInterest), [{'user_id': user_id, 'topic_id': topic} for topic in topics])
    if values:
        conn.execute(update(StudentProfile).where(StudentProfile.user_id == user_id).values(**values))
    return read_profile(conn, user_id)
