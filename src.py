import os

from sqlalchemy import null
from app import app
import urllib.request
import sqlite3
import boto3
import json
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory, send_file, jsonify, g, abort
from werkzeug.utils import secure_filename
from PIL import Image

#download, thumbnail, delete, select, sqlite, google vision ai, list images

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
conn = sqlite3.connect('pic_gallery.db')

DATABASE = 'pic_gallery.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

f = open('creds.json')
creds = json.load(f)

def upload_s3(filepath, username, filename):
    BUCKET = creds['s3_creds'][0]["BUCKET"]
    ACCESS_KEY = creds['s3_creds'][0]["ACCESS_KEY"]
    SECRET_KEY = creds['s3_creds'][0]["SECRET_KEY"]
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,aws_secret_access_key=SECRET_KEY)

    s3.upload_file(filepath, BUCKET, username + '/' + filename)

def list_s3():
    BUCKET = creds['s3_creds'][0]["BUCKET"]
    ACCESS_KEY = creds['s3_creds'][0]["ACCESS_KEY"]
    SECRET_KEY = creds['s3_creds'][0]["SECRET_KEY"]
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,aws_secret_access_key=SECRET_KEY)
    contents = []
    ret_val = []
    for item in s3.list_objects(Bucket=BUCKET)['Contents']:
        contents.append(item)
    return contents
def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
	

# Check user in database
def auth_check(auth_query, password):
    con = get_db()
    cur = get_db().cursor()

    cur.execute(auth_query)
    rows = cur.fetchall()
    if rows == []:
        con.commit()
        return 'Wrong username'
    else:
        if password != rows[0][2]:
            con.commit()
            return 'Wrong password'
    con.commit()
    return 1


# Create user and write to database
@app.route('/create_user', methods=['GET'])
def create_user():
    
    args = request.args
    name = args.get('name', type=str)
    password = args.get('password', type=str)
    #conn.execute("INSERT INTO USERS (NAME, PASSWORD ) VALUES (" + name + ", " + password ")")
    query = 'INSERT INTO USERS(NAME,PASSWORD) VALUES("'  + name + '", "' + password + '")'
    con = get_db()
    cur = get_db().cursor()
    cur.execute(query)
    con.commit()
    path = './userdirs/' + name
    thumbnail_path = './thumbnails/' + name
    if not os.path.exists(path):
        os.makedirs(path)
        os.makedirs(thumbnail_path)
    return 'Created user'

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(name)


# Downloads all posts belonging to user, returns s3 elements of the user. Will add topic filtering in the future
@app.route('/download_posts', methods=['GET'])
def download_posts():
    name = request.args.get('name', type=str)
    password = request.args.get('password', type=str)
    post_topic = request.args.get('topic', type=str)
    print(post_topic)
    posts = []
    contents = list_s3()
    for c in contents:
        key = c['Key']
        username = key.split('/')[0]
        if username == name:
            BUCKET = creds['s3_creds'][0]["BUCKET"]
            ACCESS_KEY = creds['s3_creds'][0]["ACCESS_KEY"]
            SECRET_KEY = creds['s3_creds'][0]["SECRET_KEY"]
            s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,aws_secret_access_key=SECRET_KEY)
            with open('downloads/' + key.split('/')[1], 'wb') as f:
                s3.download_fileobj(BUCKET, key, f)
                posts.append(c)
    return jsonify(posts)

@app.route('/download_key', methods=['GET'])
def download_key():
    name = request.args.get('name', type=str)
    password = request.args.get('password', type=str)
    key = request.args.get('key', type=str)
    con = get_db()
    cur = get_db().cursor()
    auth_query = 'SELECT * FROM USERS WHERE NAME="' + name + '";'

    res = auth_check(auth_query, password)
    if res != 1:
        abort(401)
    
    post_check_query = 'SELECT * FROM POSTS WHERE USER_NAME="' + name  + '";'
    contents = cur.execute(post_check_query)
    con.commit()
    if contents == []:
        abort(401)
    else:
        try:
            BUCKET = creds['s3_creds'][0]["BUCKET"]
            ACCESS_KEY = creds['s3_creds'][0]["ACCESS_KEY"]
            SECRET_KEY = creds['s3_creds'][0]["SECRET_KEY"]
            s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,aws_secret_access_key=SECRET_KEY)
            with open('downloads/' + key.split('/')[1], 'wb') as f:
                s3.download_fileobj(BUCKET, key, f)
        except:
            return 'No such object'

    return 'Object ' + key + ' downloaded.'


@app.route('/list_posts', methods=['GET'])
def list_posts():
    name = request.args.get('name', type=str)
    password = request.args.get('password', type=str)
    post_topic = request.args.get('topic', type=str)
    con = get_db()
    cur = get_db().cursor()
    auth_query = 'SELECT * FROM USERS WHERE NAME="' + name + '";'

    res = auth_check(auth_query, password)
    if res != 1:
        abort(401)
        
    post_query = 'SELECT * FROM POSTS WHERE USER_NAME="' + name  + '";'
    posts = []
    contents = cur.execute(post_query)
    con.commit()
    for c in contents:
        posts.append(c)
        print(c)
    return jsonify(posts)



# Upload image to s3 and insert post to posts table
@app.route('/upload_post', methods=['GET', 'POST'])
def upload_file():
    name = request.args.get('name', type=str)
    password = request.args.get('password', type=str)
    post_topic = request.args.get('topic', type=str)
    if post_topic == null:
        post_topic = ''
#    if not os.path.exists('./userdirs/' + name):
#        return 'sen kimsin'

    auth_query = 'SELECT * FROM USERS WHERE NAME="' + name + '";'

    res = auth_check(auth_query, password)
    if res != 1:
        abort(401)

    con = get_db()
    cur = get_db().cursor()
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join('userdirs/' + name + '/', filename))
            image = Image.open('userdirs/' + name + '/' + filename)
            image.thumbnail((400,400))
            image.save('thumbnails/' + name + '/' + filename, optimize=True, quality=40)
            upload_s3('thumbnails/' + name + '/' + filename, 'thumbnails/' + name, filename)
            upload_s3('userdirs/' + name + '/' + filename, name, filename)
            post_query = 'INSERT INTO POSTS(NAME, USER_NAME, POST_TAG, S3_KEY) VALUES("'  + filename + '", "' + name + '", "' + str(post_topic) + '", "' + name + '/' + filename + '")'
            cur.execute(post_query)
            con.commit()
            return send_file('./userdirs/' + name + '/' + filename)
    return '''
    <!doctype html>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

if __name__ == "__main__":
    app.run()