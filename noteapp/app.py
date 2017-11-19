from functools import wraps

import flask
from werkzeug.security import generate_password_hash, check_password_hash

from flask_wtf import FlaskForm
from wtforms.fields import StringField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, EqualTo

from flask_pymongo import PyMongo

class RegisterForm(FlaskForm):
    user_id = StringField('아이디', validators=[DataRequired()])
    user_name = StringField('이름', validators=[DataRequired()])
    user_pw = PasswordField('비밀번호', validators=[DataRequired()])
    user_pw_re = PasswordField('비밀번호 확인',
        validators=[DataRequired(), EqualTo('user_pw')])

class LoginForm(FlaskForm):
    user_id = StringField('아이디', validators=[DataRequired()])
    user_pw = PasswordField('비밀번호', validators=[DataRequired()])

class NewNoteForm(FlaskForm):
    to = StringField('받는 사람', validators=[DataRequired()])
    title = StringField('제목', validators=[DataRequired()])
    content = TextAreaField('내용', validators=[DataRequired()])

def login_required(view):
    @wraps(view)
    def decorated_view(*args, **kwargs):
        if 'user' not in flask.session:
            flask.flash('로그인을 해주세요.', 'error')
            return flask.redirect(flask.url_for('login'))

        return view(*args, **kwargs)
    return decorated_view

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = 'kkdffkdgfdgkdfkg'
app.config['MONGO_DBNAME'] = 'test'

mongo = PyMongo(app)

@app.route('/')
def index():
    return flask.render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in flask.session:
        flask.flash('이미 로그인 되어 있습니다.', 'info')
        return flask.redirect(flask.url_for('index'))

    register_form = RegisterForm()
    if flask.request.method == 'POST' and register_form.validate():
        user_id = register_form.user_id.data
        user_name = register_form.user_name.data
        user_pw = register_form.user_pw.data

        if mongo.db.users.count({'id': user_id}) != 0:
            flask.flash('이미 존재하는 아이디입니다.', 'error')
            return flask.redirect(flask.url_for('register'))

        mongo.db.users.insert_one({
            'id': user_id,
            'name': user_name,
            'pw_hash': generate_password_hash(user_pw),
        })

        flask.flash('회원가입이 완료되었습니다.', 'success')
        return flask.redirect(flask.url_for('index'))

    return flask.render_template('register.html', register_form=register_form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in flask.session:
        flask.flash('이미 로그인 되어 있습니다.', 'info')
        return flask.redirect(flask.url_for('index'))

    login_form = LoginForm()
    if flask.request.method == 'POST' and login_form.validate():
        user_id = login_form.user_id.data
        user_pw = login_form.user_pw.data

        user = mongo.db.users.find_one({'id': user_id})
        if not user:
            flask.flash('존재하지 않는 아이디입니다.', 'error')
            return flask.redirect(flask.url_for('login'))

        if check_password_hash(user['pw_hash'], user_pw):
            flask.session['user'] = {
                'id': user['id'],
                'name': user['name'],
            }
            return flask.redirect(flask.url_for('index'))
        else:
            flask.flash('비밀번호가 틀렸습니다.', 'error')
            return flask.redirect(flask.url_for('login'))

        return flask.redirect(flask.url_for('index'))

    return flask.render_template('login.html', login_form=login_form)

@app.route('/logout')
def logout():
    flask.session.pop('user', None)
    return flask.redirect(flask.url_for('index'))

@app.route('/note/new', methods=['GET', 'POST'])
@login_required
def write_note():
    new_note_form = NewNoteForm()
    if flask.request.method == 'POST' and new_note_form.validate():
        to = new_note_form.to.data
        title = new_note_form.title.data
        content = new_note_form.content.data

        user = mongo.db.users.find_one({'id': to})
        if not user:
            flask.flash('존재하지 않는 사용자입니다.', 'error')
            return flask.redirect(flask.url_for('write_note'))

        mongo.db.notes.insert_one({
            'to': {
                'id': to,
                'name': user['name'],
            },
            'sender': {
                'id': flask.session['user']['id'],
                'name': flask.session['user']['name'],
            },
            'title': title,
            'content': content,
        })

        flask.flash('쪽지를 보냈습니다.', 'success')
        return flask.redirect(flask.url_for('note_list', box='outbox'))

    return flask.render_template('new_note.html', new_note_form=new_note_form)

@app.route('/note/<box>')
@login_required
def note_list(box):
    if box == 'inbox':
        notes = mongo.db.notes.find({'to.id': flask.session['user']['id']})
    elif box == 'outbox':
        notes = mongo.db.notes.find({'sender.id': flask.session['user']['id']})
    else:
        flask.abort(404)

    return flask.render_template('note_list.html', box=box, notes=notes)

@app.route('/note/content/<ObjectId:id>')
@login_required
def note_content(id):
    note = mongo.db.notes.find_one_or_404({'_id': id})

    if (flask.session['user']['id'] != note['to']['id'] and
        flask.session['user']['id'] != note['sender']['id']):
        flask.flash('자신의 쪽지만 볼 수 있습니다.', 'error')
        return flask.redirect(flask.url_for('note_list', box='inbox'))

    return flask.render_template('note_content.html', note=note)
