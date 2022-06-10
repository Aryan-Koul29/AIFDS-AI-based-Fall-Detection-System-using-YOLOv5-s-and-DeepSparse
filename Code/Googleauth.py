from email.mime.base import MIMEBase
from Google import Create_Service
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import os
import time

CLIENT_SECRET_FILE = "client_secret.json"
API_NAME = "gmail"
API_VERSION = "v1"
SCOPES = ['https://mail.google.com/']
# service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)
file = r"fallenimage.jpg"


def send_mail(email,service,lock,fallen_counter):
    if fallen_counter==1:
        msg = str(fallen_counter)+' person fell.You can dial 102 to call an Ambulance'
    else:
        msg = str(fallen_counter)+' people fell.You can dial 102 to call an Ambulance'
    lock.acquire(False)
    mimeMessage = MIMEMultipart(msg,'plain')
    mimeMessage['to'] = email
    mimeMessage['subject'] = 'A Fall has been detected!!!'
    mimeMessage.attach(MIMEText(msg,'plain'))

    content_type, encoding = mimetypes.guess_type(file)
    main_type , sub_type = content_type.split('/',1)
    file_name = os.path.basename(file)
    # print(filename)
    f = open(file,'rb')
    myFile = MIMEBase(main_type,sub_type)
    myFile.set_payload(f.read())
    myFile.add_header("Content-Disposition","attachment",filename="Fall_Detected.jpg")
    encoders.encode_base64(myFile)

    f.close()

    mimeMessage.attach(myFile)

    #print(mimeMessage.as_bytes())
    #print(base64.urlsafe_b64decode((mimeMessage.as_bytes()).encode('utf-8')).decode())
    raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

    message = service.users().messages().send(userId='me', body={'raw':raw_string}).execute()
    print(message,"fall detected")
    time.sleep(60)
    lock.release()
    print("released")

# send_mail("madhurthakkar247@gmail.com",service,1)