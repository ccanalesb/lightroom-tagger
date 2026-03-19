from flask_socketio import emit, join_room, leave_room

def register_socket_events(socketio):
    @socketio.on('connect')
    def handle_connect():
        emit('connected', {'status': 'ok'})

    @socketio.on('disconnect')
    def handle_disconnect():
        pass

    @socketio.on('subscribe_job')
    def handle_subscribe_job(data):
        job_id = data.get('job_id')
        if job_id:
            join_room(f'job_{job_id}')
            emit('subscribed', {'job_id': job_id})

    @socketio.on('unsubscribe_job')
    def handle_unsubscribe_job(data):
        job_id = data.get('job_id')
        if job_id:
            leave_room(f'job_{job_id}')
            emit('unsubscribed', {'job_id': job_id})

    @socketio.on('cancel_job')
    def handle_cancel_job(data):
        job_id = data.get('job_id')
        emit('job_cancel_requested', {'job_id': job_id})