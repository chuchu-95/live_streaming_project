from matplotlib.cbook import violin_stats
import pymysql
import uuid
from sympy import arg
import tornado.web
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application
from tornado.options import define, options
from tornado.websocket import WebSocketHandler
import datetime
import multiprocessing
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
import os
import sys
import re
import subprocess
import socket

database_settings = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "root",
    "db": "liveStreaming",
    "charset": "utf8" 
}

message_data={}

dict_sessions = {}
class BaseHandler(RequestHandler):
    # current_user为 RequestHandler里的属性，为只读，因此需要使用get_current_user()方法为其赋值。
    def get_current_user(self):
        #print(dict_sessions)
        session_id = self.get_secure_cookie("session")
        if session_id is None:
            return
        session = session_id.decode("utf-8")
        if session not in dict_sessions:
            return
        return dict_sessions[session]

# login
class LoginHandler(BaseHandler):
    def get(self):
        self.render('admin/login.html',flag=0)
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
                
        db_connect = pymysql.connect(**database_settings)
        cursor = db_connect.cursor()
        select_sql = 'select * from userTable where username="{}"'.format(username)
        cursor.execute(select_sql)
        db_connect.close()
        result = cursor.fetchall()

        if result is ():
            # self.write('用户不存在')
            # self.get()
            self.render('admin/login.html',flag=1)
        else:
            user_info = result[0]
            if username == user_info[0] and password == user_info[1]:
                self.set_secure_cookie('nickname',username)
                # create a dict to store room
                if(username not in message_data):
                    message_data[username]={}
                self.redirect('/createClass')
                # self.write('登陆成功<br><br>用户: {}<br>密码: {}<br>登录地ip: {}'
                #            .format(username, password, self.request.remote_ip))
                
                # cookie security
                session_id = str(uuid.uuid4())
                self.set_secure_cookie("session", session_id)
                dict_sessions[self.get_secure_cookie("session").decode("utf-8")] = username
            else:
                self.render('admin/login.html',flag=2)
                # self.write('用户名或密码错误')
                # self.get()

# register
class RegisterHandler(BaseHandler):
    def get(self):
        self.render('admin/register.html',flag=0)
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        id = self.get_argument('id')
        if len(username) > 10 or len(username) <= 0 or len(password) <= 0:
            # self.write('注册失败，用户名长度：1~10，密码长度 > 0')
            # self.get()
            self.render('admin/register.html',flag=1)
        else:
            db_connect = pymysql.connect(**database_settings)
            cursor = db_connect.cursor()
            select_sql = 'select username from userTable where username="{}"'.format(username)
            select_sqp2= 'select id from userTable where id="{}"'.format(id)

            cursor.execute(select_sql)
            name_line = cursor.fetchall()

            cursor.execute(select_sqp2)
            id_line = cursor.fetchall()

            #judge if username exists or id exists
            if(len(name_line) > 0):
                db_connect.close()
                self.render('admin/register.html',flag=2)
            elif(len(id_line) > 0):
                db_connect.close()
                self.render('admin/register.html',flag=3)
            else:
                insert_sql = 'insert into userTable values("{}","{}","{}")'.format(username, password, id)
                cursor.execute(insert_sql)
                db_connect.commit()
                #self.write('注册成功')
                self.render('admin/login.html',flag=3)

                db_connect.close()


classRoomDict = {}
define("judgeName", type=int, default=0)

class CreateClassHandler(BaseHandler):
    # flag=1->create    flag=2->enter
    # judgeName: judge if a class exists
    @tornado.web.authenticated
    def get(self):
        db_connect = pymysql.connect(**database_settings)
        cursor = db_connect.cursor()
        #list classes at front-page
        select_sql = 'select * from classtable'
        count = cursor.execute(select_sql) #the execute times
        print(count)
        result = cursor.fetchall()  # 取出所有行
        for res in result:            # 打印结果 typr(i) = tuple
            #id, teacherId, className, classCode, createDate, teacherName
            id = res[0]
            curDict = {"className": res[2], "teacherName": res[5], "members": [res[5]]} 
            classRoomDict[id] = curDict
        print(classRoomDict)
        self.render('front-page/front-page.html',classList=classRoomDict, judge=options.judgeName)
        options.judgeName = 0
        db_connect.close()

    def post(self):
        #create a new class
        newClassName = self.get_argument("newClassName")
        teacherName = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
        # store to db
        db_connect = pymysql.connect(**database_settings)
        cursor = db_connect.cursor()
        insert_sql = 'insert into classtable(className, teacherName) values("{}","{}")'.format(newClassName, teacherName)
        cursor.execute(insert_sql)
        db_connect.commit()
        # get the insert data
        select_sql = 'select * from classtable order by id desc limit 1'
        cursor.execute(select_sql)
        result = cursor.fetchone()
        #print(result)
        classRoomDict[result[0]] = {"className": result[2], "teacherName": result[5], "members": [result[5]]}
        self.render('front-page/front-page.html', classList=classRoomDict, judge=options.judgeName)
        db_connect.close()

#delete class
class DeleteClassHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        id = self.get_argument('id')
        creater = classRoomDict[int(id)]["teacherName"]
        user = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
        if user != creater:
            self.render('front-page/front-page.html', classList=classRoomDict, judge=2)
        else:
            db_connect = pymysql.connect(**database_settings)
            cursor = db_connect.cursor()
            #list classes at front-page
            delete_sql = 'delete from classtable where id="{}"'.format(id)
            cnt = cursor.execute(delete_sql) #the execute times
            db_connect.commit()
            print(id)
            print("=====after delete========")
            #del classRoomDict[id]
            db_connect.close()   
            delId = int(id)
            print(classRoomDict) 
            print(classRoomDict[delId])
            print("================")
            del classRoomDict[delId]    
            self.redirect("/createClass")

#values that after /enter and redirect should be transported
define("roomId", type=int)
define("roomName", type=str)

class EnterClassHandler(BaseHandler):
    # jump to class
    @tornado.web.authenticated
    def get(self):
        id = int(self.get_argument('id'))
        db_connect = pymysql.connect(**database_settings)
        cursor = db_connect.cursor()
        select_sql = 'select * from classtable where id = "{}"'.format(id)
        cursor.execute(select_sql)
        result = cursor.fetchone()
        db_connect.close()
        #id, teacherId, className, classCode, createDate, teacherName
        targetName = result[5]
        userName = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
        if(id not in message_data[userName]):
            message_data[userName][id]=[]
        print("meassage_data")
        print(message_data)
        options.roomId = id
        options.roomName = result[2]
        # #teacher
        # if targetName == userName:
        #     # self.render('teacher/teacher.html', room_name=result[2], room_id=id,nick_name=userName,creater=targetName, all_users=classRoomDict[id]["members"])
        #     self.redirect('/class')
        # #student
        # else:
        #     self.render('student/student.html')
        self.redirect('/class')
    def post(self):
        className = self.get_argument('className')
        db_connect = pymysql.connect(**database_settings)
        cursor = db_connect.cursor()
        select_sql = 'select id from classtable where className = "{}"'.format(className)
        cursor.execute(select_sql)
        result = cursor.fetchone()
        db_connect.close()
        # print("==========")
        # print(result)
        if not result:
            options.judgeName = 1
            self.redirect("/createClass")
        else:
            id = int(result[0])
            userName = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
            if(id not in message_data[userName]):
                message_data[userName][id]=[]
            #id, teacherId, className, classCode, createDate, teacherName
            options.roomId = id
            options.roomName = className
            self.redirect('/class')

statPush = {} #key: creater+roomid(id) value: stat -1 0 1 2(close none screen camera)   
class ClassHandler(BaseHandler):
    #render teacher and student.html
    @tornado.web.authenticated
    def get(self):
        roomid = options.roomId
        user = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
        
        sStat = "Share Screen"
        cStat = "Open"
        aStat = "Open"
        p = "teacher"
        if user != classRoomDict[roomid]["teacherName"]:
            p = "student"
        #change open or close
        judgeStat = p+str(roomid)
        if judgeStat in statPush:
            if statPush[judgeStat] != 0:
                if statPush[judgeStat] == 1:
                    sStat = "Close Screen"
                elif statPush[judgeStat] == 2:
                    cStat = "Close"
                elif statPush[judgeStat] > 2:
                    aStat = "Close"
                    if statPush[judgeStat] == 3:
                        sStat = "Close Screen"
                    elif statPush[judgeStat] == 4:
                        cStat = "Close"
        print("========push stat========")
        print(statPush)
        self.render('teacher/teacher.html',
            nick_name = user,
            room_name = options.roomName, 
            room_id=roomid,
            message = message_data[user][roomid],
            flag = 0,
            all_users = classRoomDict[roomid]["members"],
            creater = classRoomDict[roomid]["teacherName"],
            screenState = sStat,
            cameraStat = cStat,
            audioState = aStat,
            )
        #print(data[str(self.current_user,encoding="utf-8")][roomid])

# 定义接收/发送聊天消息的视图处理类，继承自websocket的WebSocketHandler
class ChatHandler(WebSocketHandler):
    users = set()  # 用来存放在线用户的容器
    rid="1"
    name=""
    def open(self):
        self.rid = options.roomId
        self.name = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
        # self.name=(str(self.get_secure_cookie('nickname'),encoding = "utf-8"))
        self.users.add(self)  # 建立连接后添加用户到容器中
        if(self.name not in classRoomDict[self.rid]["members"]):
            classRoomDict[self.rid]["members"].append(self.name)

        d0={'from':'sys','roomid':self.rid,'msg':u"%s-[%s]-进入聊天室" % (self.name, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
        
        for u in self.users:  # 向已在线用户发送消息
            u.write_message(d0)
            u.write_message({'from':'users','roomid':self.rid,'msg':classRoomDict[self.rid]["members"]})

    def on_message(self, message):
        
        #name=(str(self.get_secure_cookie('nickname'),encoding = "utf-8"))
        #存聊天记录 ,处理带有艾特的信息
        
        if(type(message).__name__=='str'):
            line1=(u"%s-[%s]-said:" % (self.name, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            line2=message
            d1={'from':self.name,'roomid':self.rid,'msg1':line1,'msg2':line2}#here!

            if(message=="\\call_teacher"):
                message_call_teacher={'from':'call_teacher','roomid':self.rid,'msg1':line1,'msg2':self.name+" 举手了！"}
                for u in self.users:
                    if(u.name==classRoomDict[self.rid]["teacherName"]):
                        u.write_message(message_call_teacher)
                           
            for u in self.users:  # 向在线用户广播消息
                #uname=str(u.get_secure_cookie('nickname'),encoding = "utf-8")
                if(message!="CPFL2FJOTQGzR/8DXZEyfAjxS9hSTk0Bs0f/A12RMnwI8UvYUk5NAbNH/wNdkTJ8"and message!="\\painter" and message!="\\call_teacher"):
                    u.write_message(d1)
                    if(u.name in classRoomDict[self.rid]["members"]):
                        message_data[u.name][self.rid].append(d1)
            
            #处理@
            index1=0
            index2=0
            callname=''
            for i in range(0,len(message)):
                if(message[i]=='@'):
                    index1=i
                    break
            for i in range(index1+1,len(message)):
                if(message[i]==' '):
                    index2=i
                    break
            callname=message[index1+1:index2]
            if(callname in classRoomDict[self.rid]["members"]):
                for u in self.users:
                    #uname=str(u.get_secure_cookie('nickname'),encoding = "utf-8")
                    
                    if(u.name==callname):
                        d_1={'from':'sys','roomid':self.rid,'msg':self.name+' @了您!'}
                        u.write_message(d_1)
                        d_2={'from':'at','roomid':self.rid,'msg':self.name+' @了您!'}
                        u.write_message(d_2)

            #////

    def on_close(self):
        #name=(str(self.get_secure_cookie('nickname'),encoding = "utf-8"))
        name=self.name
        self.users.remove(self) # 用户关闭连接后从容器中移除用户
        classRoomDict[options.roomId]["members"].remove(self.name)
        d={'from':'sys','roomid':self.rid,'msg':u"%s-[%s]-离开聊天室" % (self.name, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
        for u in self.users:
            u.write_message(d)
            u.write_message({'from':'users','roomid':self.rid,'msg':classRoomDict[self.rid]["members"]})
        
    def check_origin(self, origin):
        return True  # 允许WebSocket的跨域请求



def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def get_device(video_list,audio_list):
    cmd = ['ffmpeg', '-list_devices','true', '-f','dshow','-i','dummy']
    process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8",
                        text=True)
    flag=0
    count=0
    for line in process.stdout:
        _line=line
        if line.startswith("[dshow") and line.endswith("o)\n"): #有效语句
            count+=1
            index = line.find("]")
            if index > 0:
                _line = line[index+2:]
        if _line.endswith("(video)\n"):
            flag=1 #1:video    2:audio
            count=-1
        if _line.endswith("(audio)\n"):  
            flag=2
        if flag==1:
            print("append video")
            print(_line)
            video_list.append(_line[1:len(_line)-10])
            flag = 0
        
        if flag==2:
            print("append audio")
            print(_line)
            audio_list.append(_line[1:len(_line)-10])
            flag = 0
    video_list.append("屏幕")
    audio_list.append("None")

def screenPush(p, roomid, ip):
    cmd=['ffmpeg','-f','gdigrab','-framerate','15','-i','desktop','-pix_fmt','yuv420p','-codec:v','libx264','-bf','0','-g','300','-f','flv','rtmp://'+ip+'/live/'+p+roomid]
    return cmd
    
def cameraPush(video, p, roomid, ip):
    cmd=['ffmpeg','-f','dshow','-i','video='+video,'-pix_fmt','yuv420p','-codec:v','libx264','-bf','0','-g','300','-f','flv','rtmp://'+ip+'/live/'+p+roomid]
    return cmd

def audioPush(video, audio, p, roomid, ip, videoState):
    curPid = pidPush[p+roomid]
    print(pidPush)
    os.system("taskkill /t /f /pid %s"%curPid)
    if videoState == 1: # screen 
        print("===========push screen========")
        cmd=['ffmpeg','-f','dshow','-i','audio='+audio,'-f','gdigrab','-framerate','15','-i','desktop','-pix_fmt','yuv420p','-codec:v','libx264','-bf','0','-g','300','-f','flv','rtmp://'+ip+'/live/'+p+roomid]
        statPush[p+roomid] = 3
    elif videoState == 2: # camera
        print("===========push camera========")
        cmd=['ffmpeg','-f','dshow','-i','video='+video+':audio='+audio,'-pix_fmt','yuv420p','-codec:v','libx264','-bf','0','-g','300','-f','flv','rtmp://'+ip+'/live/'+p+roomid]
        statPush[p+roomid] = 4
    # cmd=['ffmpeg','-f','dshow','-i','audio='+audio,'-codec:a','aac','-ac','2','-ar','44100','-f','flv','rtmp://'+ip+'/live/'+p+roomid]
    return cmd

#video_list[0] camera  video_list[1] screen
#audio_list[0]
# define("shareStat", type=int,default=-1)
pidPush = {} #key: creater+roomid(id) value: pid
class PushHandler(BaseHandler):
    #judge student or teacher
    def push(self, id, creater, btn):
        self.video_list = [] 
        self.audio_list = []
        get_device(self.video_list,self.audio_list)
        stat = statPush[creater+id]
        # if stat < 1 and btn != 'audio':
        if stat == 0 or (btn == 'audio' and stat > 0 and stat < 3):
            self.initPush(id, creater, btn)
        else:
            # self.process.kill()
            curPid = pidPush[creater+id]
            print(pidPush)
            os.system("taskkill /t /f /pid %s"%curPid)
            if btn == 'audio' and stat > 2:
                if stat == 3:
                    self.initPush(id, creater, 'screen')
                elif stat == 4:
                    self.initPush(id, creater, 'video')
            else:
                statPush[creater+id] = 0
        # statPush[creater+id] *= -1
    
    def initPush(self, id, creater, btn):
        ip=get_host_ip()
        if btn == 'screen':
            cmd = screenPush(creater, id, ip)
            self.process = subprocess.Popen(cmd, shell=False,encoding="utf-8")
            pidPush[creater+id] = self.process.pid
            statPush[creater+id] = 1
        elif btn == 'video':
            cmd = cameraPush(self.video_list[0], creater, id, ip)
            self.process = subprocess.Popen(cmd, shell=False,encoding="utf-8")
            pidPush[creater+id] = self.process.pid
            statPush[creater+id] = 2
        elif btn == 'audio':
            judge = statPush[creater+id]
            cmd = audioPush(self.video_list[0],self.audio_list[0], creater, id, ip, judge)
            self.process = subprocess.Popen(cmd, shell=False,encoding="utf-8")
            pidPush[creater+id] = self.process.pid
            
    def get(self):  
        id = self.get_argument('roomId')
        judge = self.get_argument('creater')
        btn = self.get_argument('btn')
        # stat = self.get_argument('stat')
        # options.shareStat *= -1
        creater = ""
        if judge == '0':
            creater = "teacher"
        elif judge == '1':
            creater = "student"
        # if options.shareStat == -1:
        #     print("=========stop=========")
        #     self.process.kill()
        # elif options.shareStat == 1:
        #     print("=========start=========")
        #     self.push(id, creater, options.shareStat)
        # self.push(id, creater, options.shareStat)
        if creater+id not in statPush:
            statPush[creater+id] = 0
        self.push(id, creater, btn)
        self.redirect('/class')
       
    
class DrawHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        userName = dict_sessions[self.get_secure_cookie("session").decode("utf-8")]
        roomid = options.roomId
        targetName = classRoomDict[roomid]["teacherName"]
        if targetName == userName:
            # self.render('teacher/teacher.html', room_name=result[2], room_id=id,nick_name=userName,creater=targetName, all_users=classRoomDict[id]["members"])
            self.render('board-io-master/teacher-draw.html')
        #student
        else:
            self.render('board-io-master/student-draw.html') 

class UserHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('front-page/front-page-user.html')
        
class ScheduleHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self): 
        self.render('front-page/front-page-schedule.html')
        
class CloudStorageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):  
        self.render('front-page/front-page-storage.html')
            
if __name__=='__main__':
    import os
    BASE_DIR=os.path.dirname(__file__)
    app=Application([
        (r'/login',LoginHandler),
        (r'/register',RegisterHandler),
        (r'/createClass',CreateClassHandler),
        (r'/deleteClass/', DeleteClassHandler),
        (r'/enterClass/',EnterClassHandler),
        (r'/chat',ChatHandler),
        (r'/class',ClassHandler),
        (r'/shareScn/', PushHandler),
        (r'/draw', DrawHandler),
        (r'/user', UserHandler),
        (r'/schedule', ScheduleHandler),
        (r'/cloudStorage', CloudStorageHandler)
    ],
    # template_path=os.path.join(BASE_DIR,'template'),
    # static_path=os.path.join(BASE_DIR,'static'),
    #default_host= "45875l24k7.zicp.vip",
    template_path='template',
    static_path='static',
    debug=True,
    login_url='/login',
    # cookie_secret='CPFL2FJOTQGzR/8DXZEyfAjxS9hSTk0Bs0f/A12RMnwI8UvYUk5NAbNH/wNdkTJ8')
    cookie_secret='SECRET_DONT_LEAK')
    server=HTTPServer(app,xheaders=True)
    server.listen(8001)
    IOLoop.current().start()