import dropbox
import os
import sys
import time
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
from datetime import datetime
dropbox_access_token= "oiMRWc9DAhoAAAAAAAAAAWALYwC53_XkoaDXh9K3AdBmraK-G4sh6a1cEPiJT3q5"
from tabulate import tabulate
import boto3
from boto3.dynamodb.conditions import Key

app = Flask(__name__,static_url_path = "/images", static_folder = "images")
flag = 0
users = {}
curr_repo = 0
curr_branch = 0
curr_folder = 0
obj2 = 0
dynamodb = boto3.resource('dynamodb',region_name='us-east-1')
#dropbox_path= "/test.py"
#computer_path="./test.py"
client = dropbox.Dropbox(dropbox_access_token)
print("[SUCCESS] dropbox account linked")

@app.route('/')
def home():
   return render_template('login.html')

@app.route('/registered',methods = ['GET', 'POST'])
def after_register():
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    if username not in users:
        put_user(username,password)
        obj2 = User(username,password,email)
        users[username] = obj2
        return render_template('login.html')
    else:
        print("User already exists!")
        return render_template('register.html')

@app.route('/success/<option>',methods = ['GET', 'POST'])
def success(option):
    global obj2
    if(option=="login"):
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            if login(username,password):
                obj2 = users[username]
                return render_template('success.html',username = username,repos = {"some":[i for i in obj2.repos]},collabs = {"some":[i for i in obj2.collabs]})
            else:
                return render_template('login.html')
    elif(option=="repocreated"):
        repo_name = request.form['repo_name']
        desc= request.form['description']
        collaborators = request.form['collaborators'].split()
        hasReadMe = int(request.form.getlist('readme')[0])
        vis = int(request.form.getlist('visibility')[0])
        obj2.createRepo(repo_name,desc,collaborators,hasReadMe,vis)
        return render_template('success.html',username = obj2.username,repos = {"some":[i for i in obj2.repos]},collabs = {"some":[i for i in obj2.collabs]})

@app.route('/change_folder',methods=['GET','POST'])
def change_folder():
    global curr_folder
    curr_folder = request.form['folder_name']
    return 'done'

@app.route('/createrepo')
def createrepo():
    return render_template('create.html')

@app.route('/delete/<name>')
def delete(name):
    obj2.deleteRepo(name)
    del_repo(name)
    return render_template('success.html',username = obj2.username,repos = {"some":[i for i in obj2.repos]},collabs = {"some":[i for i in obj2.collabs]})


@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/repo/<name>')
def repo(name):
    global curr_repo
    if name in obj2.repos:
        curr_repo = obj2.repos[name]
    else:
        curr_repo = obj2.collabs[name]
    return render_template('repo.html',branches = [i for i in curr_repo.branches])

@app.route('/change_branch',methods = ['GET', 'POST'])
def change_branch():
    global curr_branch
    curr_branch = curr_repo.branches[request.form['branch']]
    folders = [i.name for i in curr_branch.folders] + [i for i in curr_branch.files]
    result = {'folders':folders}
    return result


@app.route('/back')
def back():
    return render_template('repo.html',branches = [i for i in curr_repo.branches])

@app.route('/homecoming')
def homecoming():
    return render_template('success.html',username = obj2.username,repos = {"some":[i for i in obj2.repos]},collabs = {"some":[i for i in obj2.collabs]})

@app.route('/push')
def push():
    return render_template('push.html')

@app.route('/afterpush',methods = ['GET', 'POST'])
def afterpush():
    folder_name = curr_folder
    desc = request.form['description']
    op = int(request.form.getlist('whichbr')[0])
    if(op==0):
        curr_repo.branches['master'].push(folder_name,desc)
    elif(op==1):
        br_name = request.form['branch_name']
        curr_repo.add_branch(br_name)
        curr_repo.branches[br_name].push(folder_name,desc)
    elif(op==2):
        curr_branch.push(folder_name,desc)
    return render_template('repo.html',branches = [i for i in curr_repo.branches])


@app.route('/pull')
def pull():
    return render_template('pull.html',repo_name = curr_repo.name,prs = {"some":[(str(i+1)+". "+curr_repo.pr[i].from_branch+"   ->   "+curr_repo.pr[i].to_branch+"Status: "+curr_repo.pr[i].status) for i in range(len(curr_repo.pr))]})

@app.route('/afterpull',methods = ['GET', 'POST'])
def afterpull():
    source = request.form['source']
    dest = request.form['destination']
    curr_repo.createPullRequest(source,dest)
    return render_template('pull.html',prs = {"some":[(str(i+1)+". "+curr_repo.pr[i].from_branch+"   ->   "+curr_repo.pr[i].to_branch+"Status: "+curr_repo.pr[i].status) for i in range(len(curr_repo.pr))]})

@app.route('/merge_request',methods = ['GET', 'POST'])
def merge_request():
    index = int(request.form['index'])
    commit_desc = request.form['desc']
    curr_repo.merge_pr(index,commit_desc)
    return render_template('pull.html',prs = {"some":[(str(i+1)+". "+curr_repo.pr[i].from_branch+"   ->   "+curr_repo.pr[i].to_branch+"Status: "+curr_repo.pr[i].status) for i in range(len(curr_repo.pr))]})

@app.route('/afterclone',methods = ['GET', 'POST'])
def afterclone():
    obj2.clone(curr_repo.name)
    return render_template('repo.html')

@app.route('/version_history')
def version():
    curr_repo.versionh.view()
    headers=['Commit no', 'Description','type','timestamp']
    return render_template('version.html',headers = headers, rows = curr_repo.versionh.strings)

def query_repo(reponame):
    table = dynamodb.Table('repos')
    response = table.query(
        KeyConditionExpression=Key('reponame').eq(reponame)
    )
    if response['Items']:
        return response['Items'][0]
    else:
        return 0

def put_repo(reponame, owner, l):
    table = dynamodb.Table('repos')
    response = table.put_item(
       Item={
            'reponame': reponame,
            'owner': owner,
            'collaborators': l
            }
    )

def del_repo(reponame):
    table = dynamodb.Table('repos')
    response = table.delete_item(
       Key={
            'reponame': reponame
            }
    )

def login(username,password):
    table = dynamodb.Table('passwd')
    response = table.query(
        KeyConditionExpression=Key('username').eq(username)
    )
    if response['Items']:
        item =  response['Items'][0]
        if item['password'] == password:
            return 1
        else:
            return 0
    else:
        return 0

def put_user(username, password):
    table = dynamodb.Table('passwd')
    response = table.put_item(
       Item={
            'username': username,
            'password': password
            }
    )

class User:

    def __init__(self, username, password, email):
        self.username = username
        self.password = password
        self.email = email
        self.repos = {}
        self.collabs = {}
        client.files_create_folder("/"+username)

    def listRepo(self):
        print("Repositories:")
        for i in self.repos:
            print(i)

    def createRepo(self,name,desc,collaborators,hasReadMe,vis):
        put_repo(name,self.username,collaborators)
        repo = Repository(self.username,name,desc,hasReadMe,vis)
        for i in collaborators:
            users[i].collabs[name] = repo
        self.repos[name] = repo


    def clone(self,rep_name):
        #rep_name = input("cloning Repository: ")
        with open(rep_name+".zip", "wb") as f:
                metadata, res = client.files_download_zip("/"+curr_repo.owner+"/"+rep_name)
                f.write(res.content)
        print("cloned!!")



    def changeProfile(self):
        pass


    def deleteRepo(self,name):
        client.files_delete("/"+self.username+"/"+name)
        for _,obj in users.items():
            if name in obj.collabs:
                del obj.collabs[name]
        del self.repos[name]

class Repository :

    def __init__(self,username,name,description,hasReadMe,visibility):
        self.owner = username
        self.name = name
        self.description = description
        self.visibility = visibility
        self.hasReadMe = hasReadMe
        self.branches = dict()
        self.no_openpr = 0
        self.no_closedpr = 0
        self.pr = []
        self.versionh = VersionHistory()
        client.files_create_folder("/" + self.owner + "/" + self.name)
        #client.files_create_folder("/" + self.owner + "/" + self.name + "/" + "master" )
        #br = Branch(self.owner,self.name,"master")
        #br.createBranchInDB()
        #self.branches["master"] = br
        self.add_branch("master")
        if(self.hasReadMe == 1):
            readme = File("readme",10,10,0,"readme")
            client.files_paper_create(b'DEFAULT README',"/" + self.owner + "/" + self.name + "/" + "master" + "/" + "README.paper", dropbox.files.ImportFormat.plain_text)
            self.branches['master'].files['readme'] = readme

    def rename(self):
        pass

    def SetVisibility(self):

        if(self.visibility == 1):
            self.visibility = 0
        else :
            self.visibility = 1


    def add_branch(self,branch_name):
        br = Branch(self.owner,self.name,branch_name,self.versionh)
        br.createBranchInDB()
        self.branches[branch_name] = br

    def listPullRequests(self):
        for i in range(len(self.pr)):
            print(i+1,". ",self.pr[i].from_branch,"   ->   ",self.pr[i].to_branch,"Status: ",self.pr[i].status)


    def createPullRequest(self, fromb, tob):
        pr = Pull_Request(self.owner,self.name, fromb, tob, self.versionh)
        self.pr.append(pr)
        self.no_openpr+=1
        print("Pull request created!")

    def merge_pr(self, index, commit_desc):
        self.pr[index-1].merge(commit_desc,self.branches)
        self.no_openpr-=1
        self.no_closedpr+=1


class Branch:

    def __init__(self,username,repo_name,branch_name,versionh):
        self.owner = username
        self.repo_name = repo_name
        self.branch_name = branch_name
        self.folders = []
        self.files = {}
        self.versionh = versionh

    def createBranchInDB(self):
          client.files_create_folder("/" + self.owner + "/" + self.repo_name + "/" + self.branch_name)

    def list_folders(self):
        response = client.files_list_folder("/" + self.owner + "/" + self.repo_name + "/" + self.branch_name)
        print(response)

    def push(self, path, commit_desc):
        commit_type = "PUSH"
        target_br = self.branch_name
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")

        modtime_epoch = os.path.getmtime(path)
        modificationTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modtime_epoch))
        to_remove = [i for i in self.folders if path == i.name.split("/")[0]]
        if to_remove:
            folder_path = "/" + self.owner + "/" + self.repo_name + "/" + self.branch_name + "/" + to_remove[0].name
            print(folder_path)
            client.files_delete(folder_path)
        for i in to_remove:
            self.folders.remove(i)
        
        for root,d_names,f_names in os.walk(path):
            folder_path = "/" + self.owner + "/" + self.repo_name + "/" + self.branch_name + "/" + root.replace("\\","/")
            r = Folder(root.replace("\\","/"), os.path.getsize(root.replace("\\","/")), modificationTime)
            self.folders.append(r)
            client.files_create_folder(folder_path)
            for file in f_names:
                if(file!=".DS_Store"): ## CONDITION NOT REQ FOR WINDOWS
                    modtime_epoch = os.path.getmtime(root.replace("\\","/")+"/"+file)
                    modificationTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modtime_epoch))
                    a,type  = os.path.splitext(root.replace("\\","/")+"/"+file)
                    f = File(file,os.path.getsize(root.replace("\\","/")+"/"+file),0,modificationTime,type)
                    self.files[root.replace("\\","/")+"/"+file]=f
                    client.files_upload(open(root.replace("\\","/")+"/"+file, "rb").read(),folder_path+"/"+file)
        '''for root,d_names,f_names in os.walk(path):
            folder_path = "/" + self.owner + "/" + self.repo_name + "/" + self.branch_name + "/" + root
            client.files_create_folder(folder_path)
            for file in f_names:
                if(file!=".DS_Store"): ## CONDITION NOT REQ FOR WINDOWS
                    modtime_epoch = os.path.getmtime(root+"/"+file)
                    modificationTime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modtime_epoch))
                    a,type  = os.path.splitext(root+"/"+file)
                    f = File(file,os.path.getsize(root+"/"+file),0,modificationTime,type)
                    self.files[file]=f
                    client.files_upload(open(root+"/"+file, "rb").read(),folder_path+"/"+file)'''

        com = Commit(commit_desc,timestamp,commit_type,target_br)
        self.versionh.commits.append(com)
        print("Pushed and commited !!\n")

class Folder:
    def __init__(self, name, size, lastEdited):
        self.name = name
        self.size = size
        self.lastEdited = lastEdited



class File:
    def __init__(self,name,size,lines,lastEdited,type):
        self.name = name
        self.size = size
        self.lines = lines
        self.lastEdited = lastEdited
        self.type = type

    def display_code(self):
        pass

class Pull_Request:
    def __init__(self, username, repo_name, from_branch, to_branch, versionh):
        self.created_by_user = username
        self.repo_name = repo_name
        self.from_branch = from_branch
        self.to_branch = to_branch
        self.status = "Open"
        self.versionh = versionh

    def merge(self,commit_desc,branches):
        commit_type = "MERGE"
        target_br = self.to_branch

        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")

        from_path = "/" + self.created_by_user + "/" + self.repo_name + "/" + self.from_branch
        to_path = "/" + self.created_by_user + "/" + self.repo_name + "/" + self.to_branch
        client.files_delete(to_path)

        client.files_copy(from_path, to_path)
        branches[target_br].folders = [i for i in branches[self.from_branch].folders]
        branches[target_br].files = {i:branches[self.from_branch].files[i] for i in branches[self.from_branch].files}
        self.status = "Closed"
        com = Commit(commit_desc,timestamp,commit_type,target_br)
        self.versionh.commits.append(com)
        print("Merged and commited !!\n")


class Commit:
    def __init__(self,commit_desc,timestamp,commit_type,source_br):
        self.commit_desc = commit_desc
        self.timestamp= timestamp
        self.commit_type = commit_type
        self.source_br = source_br

class VersionHistory:
    def __init__(self):
        self.commits = []
        self.strings = []
    def view(self):
        self.strings = []
        for i in range(len(self.commits),0,-1):
            self.strings.append([i,self.commits[i-1].commit_desc,self.commits[i-1].commit_type,self.commits[i-1].timestamp])

if __name__ == '__main__':
   app.run(debug = True)
