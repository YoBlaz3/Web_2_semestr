from ntpath import join
from flask import Flask, render_template, request, abort, send_from_directory, session, send_file
from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import distinct, desc
from flask_login import current_user, login_required, LoginManager
import io
import datetime

app = Flask(__name__)
application = app


login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа к данной странице необходимо пройти процедуру аутентификации'
login_manager.login_message_category = 'warning'


app.config.from_pyfile('config.py')

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db)

from auth import bp as auth_bp, init_login_manager
from book import bp as book_bp
from tools import BooksFilter

app.register_blueprint(auth_bp)
app.register_blueprint(book_bp)

init_login_manager(app)

from models import *

PER_PAGE = 10

def convert_to_csv(records):
    result = f'{records}'
    return result

def generate_report(records):
    buffer = io.BytesIO()
    buffer.write(convert_to_csv(records).encode('utf-8'))
    buffer.seek(0)
    return buffer


@app.route('/')
def index():
    genres = Genre.query.all()
    book_genre = Book_Genre.query.all()
    years = db.session.query(distinct(Book.year)).order_by(desc(Book.year)).all()
    years = [str(i[0]) for i in years]
    page = request.args.get('page', 1, type=int)
    title = request.args.get('title', '')
    genres_list = request.args.getlist('genre_id')
    years_list = request.args.getlist('year')
    amount_from = request.args.get('amount_from', '')
    amount_to = request.args.get('amount_to', '')
    author = request.args.get('author', '')
    books = BooksFilter().perform(title, genres_list, years_list, amount_from, amount_to, author)
    pagination = books.paginate(page = page, per_page = PER_PAGE)   
    books = pagination.items
    flag = True
    if books == []:
        flag = False
    rating=Book.rating
    return render_template('index.html', books=books, genres=genres, years=years, book_genre=book_genre, pagination=pagination, rating=rating,
     title=title, genres_list=[int(x) for x in genres_list], years_list=years_list, amount_from=amount_from, amount_to=amount_to, author=author, flag=flag)
        
            



@app.route('/media/images/<cover_id>')
def image(cover_id):
    cover = Cover.query.get(cover_id)
    if cover is None:
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], cover.storage_filename)

@app.route('/popular_books')
def popular_books():
    allBooksId = []
    unique_set_int = []
    if current_user.is_authenticated:
        visits = Visits.query.all()
        for allvisits in range(len(visits)):
            x = str(visits[allvisits])
            allBooksId.append(int(x))
        unique_set = list(set(allBooksId))
        for k in range(len(unique_set)):
            c = str(unique_set[k])
            unique_set_int.append(int(c))
        for unique_id in range(len(unique_set_int)):
            book_id = allBooksId.count(unique_set_int[unique_id])
            Book.query.filter_by(id=unique_set_int[unique_id]).update(dict(visits_count=book_id))
            Book.query.order_by(Book.visits_count.desc())
            db.session.commit()
    genres = Genre.query.all()
    book_genre = Book_Genre.query.all()
    title = request.args.get('title', '')
    genres_list = request.args.getlist('genre_id')
    years_list = request.args.getlist('year')   
    amount_from = request.args.get('amount_from', '')
    amount_to = request.args.get('amount_to', '')
    author = request.args.get('author', '')
    if request.args.get('download_csv'):
        f = generate_report(str(visits))
        filename = datetime.datetime.now().strftime('%d_%m_%Y+%H_%M_%S') + '_visits_stat.csv'
        return send_file(f, mimetype='text/csv', as_attachment=True, download_name=filename)
    books = BooksFilter().perform(title, genres_list, years_list, amount_from, amount_to, author).limit(5)
    return render_template('popular_books.html', books=books, genres=genres, book_genre=book_genre)

@app.route('/last_visits')
def last_visits():
    books = []
    visits = Visits.query.filter_by(user_id = current_user.get_id()).all()
    reversed_visits = visits[::-1]
    k = 0
    if len(reversed_visits) > 5:
        while len(books) < 5:
            visit = reversed_visits[k]
            if Book.query.filter_by(id=visit.book_id).first() is not None:
                books.append(Book.query.filter_by(id=visit.book_id).first())
            k+=1
    else:
        for visit in reversed_visits:
            if Book.query.filter_by(id=visit.book_id).first() is not None:
                books.append(Book.query.filter_by(id=visit.book_id).first())
    genres = Genre.query.all()
    book_genre = Book_Genre.query.all()
    return render_template('last_visits.html', books=books, genres=genres, book_genre=book_genre)

PER_PAGE2 = 10


@app.route('/journal')
@login_required
def journal():
    dataToCvsList =[]
    dataToCvs = Visits.query.all()
    for data in dataToCvs:
        dataToCvsList.append(f'{data.id} {data.path} {data.id} {data.created_at} {data.book_id} {data.book_name}')
    visits = Visits.query.order_by(Visits.created_at.desc())
    if request.args.get('download_csv'):
        f = generate_report(dataToCvsList)
        filename = datetime.datetime.now().strftime('%d_%m_%Y+%H_%M_%S') + '_visits_stat.csv'
        return send_file(f, mimetype='text/csv', as_attachment=True, download_name=filename)
    page = request.args.get('page', 1, type=int)
    pagination = visits.paginate(page=page, per_page=PER_PAGE2)
    visits = pagination.items
    return render_template('journal.html', info=visits, pagination=pagination)

PER_PAGE3 = 10
@app.route('/stat')
def stat():
    stat = Book.query.order_by(Book.visits_count.desc())
    page = request.args.get('page', 1, type=int)
    pagination = stat.paginate(page=page, per_page=PER_PAGE3)
    stat = pagination.items 
    return render_template('stat.html', allstat=stat, pagination=pagination)    

