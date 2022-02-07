import os
from re import U
from app import app
import urllib.request
import boto3
import json
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory, send_file
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

f = open('creds.json')
creds = json.load(f)

def upload_s3(filepath, username, filename):
    BUCKET = creds['s3_creds'][0]["BUCKET"]
    ACCESS_KEY = creds['s3_creds'][0]["ACCESS_KEY"]
    SECRET_KEY = creds['s3_creds'][0]["SECRET_KEY"]
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY,aws_secret_access_key=SECRET_KEY)

    s3.upload_file(filepath, BUCKET, username + '/' + filename)


def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
	
@app.route('/create_user', methods=['GET'])
def create_user():
    args = request.args
    name = args.get('name', type=str)
    path = './userdirs/' + name
    if not os.path.exists(path):
        os.makedirs(path)
    return 'Created user'

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(name)


@app.route('/upload_post', methods=['GET', 'POST'])
def upload_file():
    name = request.args.get('name', type=str)
    if not os.path.exists('./userdirs/' + name):
        return 'sen kimsin'
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
            upload_s3('userdirs/' + name + '/' + filename, name, filename)
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