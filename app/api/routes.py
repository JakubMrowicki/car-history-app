from app.api import bp

@bp.route('/ping')
def ping():
    return {'message': 'pong'} 