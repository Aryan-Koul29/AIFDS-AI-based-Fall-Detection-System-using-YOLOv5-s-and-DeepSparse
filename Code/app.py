from sys import stdout
import logging
from flask import Flask, render_template, session, request, flash
from flask_socketio import SocketIO, emit, disconnect
from flask_session import Session
from flask_mysqldb import MySQL
import random
import bcrypt
# from camera import Camera
from utils import base64_to_pil_image
import cv2
from email.mime.text import MIMEText
import secrets
import numpy as np
import base64
from annotate import (_get_save_dir, annotate, _load_model)
import argparse
from Google import Create_Service
from deepsparse_utils import (
    YoloPostprocessor, re_init_counter
)


app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(stdout))
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'aissdb'

mysql = MySQL(app)
app.secret_key = secrets.token_bytes(16)
app.config['DEBUG'] = True
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = "filesystem"
Session(app)

CLIENT_SECRET_FILE = "client_secret.json"
API_NAME = "gmail"
API_VERSION = "v1"
SCOPES = ['https://mail.google.com/']
service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

socketio = SocketIO(app,server_options={"ws-engine":"ws"})
# camera = Camera()
args = argparse.Namespace(device=None, engine='deepsparse', fp16=False, image_shape=[
                          416, 416], model_config=None, model_filepath='zoo:cv/detection/yolov5-s/pytorch/ultralytics/coco/pruned_quant-aggressive_94', name=None, no_save=True, num_cores=None, quantized_inputs=True, save_dir='annotation_results', source='0', target_fps=None)
model, has_postprocessing = _load_model(args)

#is_webcam = args.source.isnumeric()

postprocessor = (
    YoloPostprocessor(args.image_shape, args.model_config)
    if not has_postprocessing
    else None
)
save_dir = _get_save_dir(args)


@socketio.on('input image', namespace='/test')
def test_message(input):
    input = input.split(",")[1]
    # camera.enqueue_input(input)
    # base_image = pil_image_to_base64(input)
    # camera.enqueue_input(base_image)
    # Do your magical Image processing here!!
    image_data = np.asarray(base64_to_pil_image(input))
    # image_data = image_data.encode("utf-8")
    # print(image_data.shape)
    # cv2.imshow("frame", image_data)
    # cv2.waitKey(1)
    cv2_img = annotate(args, postprocessor, image_data, model, save_dir,service,email=session.get('email'))
    
    # print("cv2_img",cv2_img)
    cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    # print(cv2_img.shape)
    # cv2.imwrite("reconstructed.jpg", cv2_img)
    retval, buffer = cv2.imencode('.jpeg', cv2_img)
    b = base64.b64encode(buffer)
    b = b.decode()
    image_data = "data:image/jpeg;base64," + b

    #print("OUTPUT " + image_data)
    emit('out-image-event', {'image_data': image_data}, namespace='/test')
    # camera.enqueue_input(base64_to_pil_image(input))

@socketio.on('connect', namespace='/test')
def test_connect():
    app.logger.info("client connected")

@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    app.logger.info("client disconnected")
    re_init_counter()
    print("client disconnected")
    disconnect(True,namespace='/test')


@app.route('/')
def index():
    session['login_status'] = False
    return render_template('index.html',status=session.get('login_status'))

@app.route('/login_index')
def login_index():
    return render_template("index.html", status=session.get('login_status'))

@app.route('/verify', methods=['GET','POST'])
def verify():
    if request.method == "POST":
        if request.form['name']!="" and request.form['email']!="" and request.form['password']!="" and request.form['con_password']!="":
            if request.form['password']==request.form['con_password']:
                ver_email = request.form['email']
                session['email'] = ver_email
                
                reg = None
                try:
                    cur = mysql.connection.cursor()
                    cur.execute("SELECT * FROM users WHERE email = '"+session.get('email')+"'")
                    reg = cur.fetchone()
                    #print(reg,session.get('email'))
                    mysql.connection.commit()
                    cur.close()
                except:
                    print(reg,session.get('email'))
                if reg is None:
                    otp_gen = random.randint(100000,999999)
                    session['otp'] = otp_gen
                    print("verify")
                    print(session.get('otp'))
                    msg="Your One Time Password for AISS is: "+str(session.get('otp'))

                    
                    mimeMessage = MIMEText(msg, 'plain')
                    mimeMessage['to'] = session.get('email')
                    mimeMessage['subject'] = 'OTP Verification'
                    mimeMessage['from'] = 'aiss50191@gmail.com'

                    raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()
                    message = service.users().messages().send(userId='me', body={'raw': raw_string}).execute()
                    print(message['id'])

                    session['name'] = request.form.get('name')
                    session['hashed'] = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
                    print("hash",session.get('hashed'))
                    return render_template("otp.html")
                else:
                    flash('This Email is already registered')
                    return render_template("login.html")
            else:
                flash('Password and Confirm Password Do not Match!')
                return render_template("login.html")
        else:
            flash('Please enter all the details properly!')
            return render_template("login.html")

@app.route('/resend_verify', methods=['GET','POST'])
def resend_verify():
    if request.method == "POST":
        #email = request.form['email']
        otp_gen = random.randint(100000,999999)
        session['otp'] = otp_gen
        print("resend")
        msg="Your One Time Password for AISS is: "+str(session.get('otp'))

        mimeMessage = MIMEText(msg, 'plain')
        mimeMessage['to'] = session.get('email')
        mimeMessage['subject'] = 'OTP Verification'
        mimeMessage['from'] = 'aiss50191@gmail.com'

        raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()
        message = service.users().messages().send(userId='me', body={'raw': raw_string}).execute()
        
        flash(u"New OTP is sent to {0}".format(session.get('email')))
        return render_template("otp.html")

@app.route('/userlogin',methods=['GET','POST'])
def userlogin():
    if request.method=='POST':
        if request.form['loginemail'] != "" and request.form['loginpass'] != "":
            email = request.form['loginemail']
            password = request.form['loginpass']
            reg = None
            try:
                cur = mysql.connection.cursor()
                cur.execute("SELECT * FROM users WHERE email = '"+email+"'")
                reg = cur.fetchone()
                session['hashed'] = reg[2].encode("utf-8")
                session['email'] = reg[1]
                session['name'] = reg[0]
                mysql.connection.commit()
                cur.close()
            except:
                pass
            if reg is None:
                flash('This Email is not registered')
                return render_template("login.html")
            else:
                if bcrypt.checkpw(password.encode('utf-8'), session.get('hashed')):
                    session['login_status'] = True
                    if session.get('login_dest')=="index":
                        return render_template("index.html",status=session.get('login_status'))
                    elif session.get('login_dest')=="falldetection":
                        return render_template("FallDetection.html")
                else:
                    flash('Incorrect Password!')
                    return render_template("login.html")
        else:
            flash('Please enter all the details properly!')
            return render_template("login.html")

@app.route('/authenticate', methods=['GET','POST'])
def authenticate():
    if request.method == "POST":
        otp_get = request.form.getlist('otp')
        otp_enter = ""
        for ele in otp_get:
            otp_enter+=str(ele)
        if len(otp_enter)<1:
            otp_enter = -1
        if int(otp_enter)==session.get('otp'):
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users VALUES('"+session.get('name')+"','"+session.get('email')+"','"+str(session.get('hashed'))[2:-1]+"')")
            mysql.connection.commit()
            cur.close()
            session['login_status'] = True
            if session.get('login_dest')=="index":
                return render_template("index.html",status=session.get('login_status'))
            elif session.get('login_dest')=="falldetection":
                return render_template("FallDetection.html")
        else:
            flash("Incorrect OTP\nTry Again!")
            return render_template("otp.html")



@app.route('/falldetection')
def falldetection():
    return render_template('FallDetection.html')


@app.route('/login/<dest>')
def login(dest):
    session['login_dest'] = dest
    return render_template("login.html")

@app.route('/contactus')
def contactus():
    return render_template("ContactUs.html",status=session.get('login_status'))

@app.route('/feedback',methods=['POST','GET'])
def feedback():
    if request.method=="POST":
        name = request.form['feed_name']
        email = request.form['feed_email']
        phone = request.form['feed_phone']
        comment = request.form['comments']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO feedback VALUES('"+name+"','"+email+"','"+phone+"','"+comment+"')")
        mysql.connection.commit()
        cur.close()
        return render_template("feedback.html")

# def gen():
#     """Video streaming generator function."""

#     app.logger.info("starting to generate frames!")
#     while True:
#         frame = camera.get_frame()  # pil_image_to_base64(camera.get_frame())

#         print(type(frame))
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


# @app.route('/video_feed')
# def video_feed():
#     """Video streaming route. Put this in the src attribute of an img tag."""
#     return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    socketio.run(app)
