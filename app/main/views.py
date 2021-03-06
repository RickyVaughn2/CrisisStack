from flask import render_template, request, redirect, url_for, flash
from werkzeug import secure_filename
from flask_login import current_user
from flask import current_app
import uuid
import os
from . import main
from ..models import Category, Application, Developer, ApplicationAssets, User
from .. import db
from .forms import ApplicationsForm, CategoryForm, ApplicationAssetsForm

ALLOWED_EXTENSIONS = set(
    ['sh', 'jpg', 'png', 'jpeg', 'svg', 'mp4', 'flv', 'mkv', '3gp']
)


def create_applications_folder(app_uuid):
    APPLICATIONS_DIR = current_app.config['APPLICATIONS_DIR']

    APP_DIR = os.path.join(APPLICATIONS_DIR, str(app_uuid))
    if not os.path.exists(APP_DIR):
        os.makedirs(APP_DIR)

    ASSETS_DIR = os.path.join(APP_DIR, 'assets')
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)

    return {'APP_DIR': APP_DIR, 'ASSETS_DIR': ASSETS_DIR}


def populate_categories(form):
    """
    Pulls choices from the database to populate our select fields.
    """
    categories = Category.query.all()
    category_names = {'0': 'Choose Category'}

    for category in categories:
        category_names[category.id] = category.name

    category_choices = [(k, v) for k, v in category_names.iteritems()]
    form.category_id.choices = category_choices


def populate_developers(form):
    """
    Pulls choices from the database to populate our select fields.
    """
    developers = Developer.query.all()
    developer_names = {'0': 'Choose Developer'}

    for developer in developers:
        developer_names[developer.user_id] = developer.name

    developer_choices = [(k, v) for k, v in developer_names.iteritems()]
    form.developer_id.choices = developer_choices


def allowed_file(filename):
    """
    Checks whether a given file extension is allowed.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def get_installed_apps():
    """
    Populate installed applications from database based on installed flag
    """
    apps = Application.query.filter_by(installed=True).all()
    return [app.uuid for app in apps]


def load_applications(**kwargs):
    """
    Populate applications from database based on parameters passed
    """
    applications = []

    apps = None

    if 'app_id' in kwargs and 'category_id' not in kwargs:
        apps = Application.query.filter_by(uuid=kwargs['app_id'])\
                                .filter_by(application_status='Active').all()
    elif 'category_id' in kwargs and 'app_id' in kwargs:
        apps = Application.query.filter_by(category_id=kwargs['category_id'])\
                                .filter(Application.uuid != kwargs['app_id'])\
                                .filter_by(application_status='Active').all()
    elif 'category_id' in kwargs and 'app_id' not in kwargs:
        apps = Application.query.filter_by(category_id=kwargs['category_id'])\
                                .filter_by(application_status='Active').all()
    else:
        apps = Application.query.all()

    for app in apps:
        assets = ApplicationAssets.query.filter_by(app_uuid=app.uuid).first()
        developer = Developer.query.filter_by(user_id=app.developer_id).first()

        app_details = {
            'id': app.id,
            'uuid': app.uuid,
            'name': app.name,
            'developer': developer.name,
            'icon': assets.icon,
            'installed': app.installed,
            'description': app.description,
            'downloads': app.downloads
        }

        applications.append(app_details)
    return applications


@main.route('/')
def index():
    installed_apps = []
    for app_uuid in get_installed_apps():
        installed_apps.append(load_applications(app_id=app_uuid))

    applications = load_applications()

    applications = [app for app in applications if app['uuid'] not in get_installed_apps()]

    return render_template('index.html',
                           root_url=current_app.config['APP_TEMPLATE_ASSESTS'],
                           applications=applications,
                           installed_apps=installed_apps)


@main.route('/app_assets/<string:app_uuid>', methods=['GET', 'POST'])
def app_assets(app_uuid):
    application = Application.query.filter_by(uuid=app_uuid).first()
    developer = Developer.query.filter_by(user_id=application.developer_id).first()

    form = ApplicationAssetsForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            APP_FOLDERS = create_applications_folder(app_uuid)
            ASSETS_DIR = APP_FOLDERS.get('ASSETS_DIR')

            app_assets = {}

            for field in form:
                if field.type == "FileField":
                    field_name = field.name
                    field_data = field.data

                    if field_data.filename == '':
                        flash('No selected file', 'error')
                        return redirect(request.url)

                    if field_data and allowed_file(field_data.filename):
                        asset_name = secure_filename(field_data.filename)
                        file_ext = asset_name.rsplit('.', 1)[1]
                        new_asset_name = field_name + '.' + file_ext
                        app_assets[field_name] = new_asset_name

                        field_data.save(os.path.join(ASSETS_DIR, asset_name))

                        file_dir = os.path.join(ASSETS_DIR, asset_name)
                        new_file_dir = os.path.join(ASSETS_DIR, new_asset_name)
                        os.rename(file_dir, new_file_dir)

            assets = ApplicationAssets(
                app_uuid=app_uuid,
                icon=app_assets.get('icon', 'app_icon.png'),
                screenShotOne=app_assets.get('screenshot1', 'browser.png'),
                screenShotTwo=app_assets.get('screenshot2', 'browser.png'),
                screenShotThree=app_assets.get('screenshot3', 'browser.png'),
                screenShotFour=app_assets.get('screenshot4', 'browser.png'),
                video=app_assets.get('video', 'None'))

            db.session.add(assets)
            db.session.commit()

            active_app = Application.query.filter_by(uuid=app_uuid).update(
                dict(application_status='Active'))

            db.session.commit()

            flash('Assets added successfully', 'success')
        return redirect(request.args.get('next') or url_for('main.index'))
    return render_template('app_assets.html', form=form, application=application, developer=developer)


@main.route('/app_info/<string:app_uuid>')
def app_info(app_uuid):
    application = Application.query.filter_by(uuid=app_uuid).first()

    app_id = application.id
    developer = Developer.query.filter_by(user_id=application.developer_id).first()
    assets = ApplicationAssets.query.filter_by(app_uuid=app_uuid).first()

    app_details = load_applications(app_id=app_uuid)
    related_apps = load_applications(category_id=application.category_id, app_id=app_uuid)

    return render_template('app_info.html',
                           root_url=current_app.config['APP_TEMPLATE_ASSESTS'],
                           app_details=app_details,
                           related_apps=related_apps, assets=assets)


@main.route('/install_app')
def install_app():
    app_id = request.args['app_id']

    try:
        app = Application.query.filter_by(uuid=app_id).update(dict(installed=True))
        db.session.commit()

        flash('Application installed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        db.session.flush()

        flash('Application did not install successfully', 'error')

    return redirect(url_for('main.index'))


@main.route('/uninstall_app')
def uninstall_app():
    app_id = request.args['app_id']

    try:
        app = Application.query.filter_by(uuid=app_id).update(dict(installed=False))
        db.session.commit()

        flash('Application uninstalled successfully', 'success')
    except Exception as e:
        db.session.rollback()
        db.session.flush()

        flash('Application did not uninstall successfully', 'error')

    return redirect(url_for('main.app_info', app_uuid=app_id))


@main.route('/launch_app')
def launch_app():
    app_id = request.args['app_id']

    try:
        pass
    except Exception as e:
        pass
    return redirect(url_for('main.index'))


@main.route('/application', methods=['GET', 'POST'])
def application():
    form = ApplicationsForm()
    populate_categories(form)
    populate_developers(form)

    if form.validate_on_submit():
        if 'app_file' not in request.files:
            flash('Application file not selected', 'error')
            return render_template('application.html', form=form)
        file = request.files['app_file']

        if file.filename == '':
            flash('Application file not selected', 'error')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            app_uuid = str(uuid.uuid4())

            APP_FOLDERS = create_applications_folder(app_uuid)

            filename = secure_filename(file.filename)
            FILE_PATH = os.path.join(APP_FOLDERS.get('APP_DIR'), filename)
            file.save(os.path.join(APP_FOLDERS.get('APP_DIR'), filename))

            size = os.stat(FILE_PATH).st_size
            app_name = filename.rsplit('.', 1)[0]

            application = Application(
                uuid=app_uuid,
                category_id=form.category_id.data,
                developer_id=form.developer_id.data,
                name=app_name,
                version=form.version.data,
                description=form.description.data,
                size=size,
                permission=form.permission.data,
                osVersion=form.osVersion.data,
                launchurl=form.launchurl.data,
                application_status='Pending')

            db.session.add(application)
            db.session.commit()

        flash('Application added successfully', 'success')
        return redirect(url_for('main.app_assets', app_uuid=application.uuid))
    return render_template('application.html', form=form)


@main.route('/category', methods=['GET', 'POST'])
def category():
    form = CategoryForm(request.form)
    categories = Category.query.all()

    if request.method == 'POST' and form.validate():
        name = form.name.data
        description = form.description.data

        category = Category(name=name, description=description)
        db.session.add(category)
        db.session.commit()

        flash('Category added successfully', 'success')
        return redirect(request.args.get('next') or url_for('main.category'))
    return render_template('category.html', form=form, categories=categories)
