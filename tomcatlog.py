# -*- coding:utf-8 -*-
import re
from collections import defaultdict
import os
import os.path
from prettytable import PrettyTable
import matplotlib.pyplot as pl
from matplotlib.ticker import MultipleLocator
import numpy as np
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import smtplib

#指定目录
g_rootdir = "./tomcatlog/"
#需要统计的字段
g_needlist = ["/update.xml", "/version.xml"]
#Y轴步长
g_Ystep = 20
#初始化数据结构
g_MailDict = defaultdict(basestring)
#文件日期
g_FileDate = ""
#初始化html语句
g_html = """\
    <html>
    <head></head>
        <body>
        %s
        </body>
    </html>
    """
#初始化body部分语句
g_body = """<p>%s</p>%s <p><img src="cid:%s"</p><hr/>"""

#取得目录下所有文件的文件名
def GetFileNames():
    files = []
    #遍历指定目录，将文件放入list
    for parent, dirnames, filenames in os.walk(g_rootdir):
        for filename in filenames:
            files.append(os.path.join(parent, filename))
    return files

#处理文件中的数据，统计文件数据的重复性
def Dealwith(file):
    with open(file) as f:
        count = defaultdict(list)
        time = "00"
        #逐行分析日志并加入字典内
        for line in f:
            match = re.search(r'(^.*) - - .*:(\d+):\d+:\d+ \+.* "\w+ (.*?) HTTP/', line)
            if match is None:
                continue
            uri = match.group(3).split('?')[0]
            if uri not in count:
                count[uri] = [['%02d'% x, 0] for x in range(24)]
            for each_list in count[uri]:
                if each_list[0] == time:
                    each_list[1] += 1
                    break
            else:
                count[uri].append([time, 1])
    #获取日志日期
    dates = re.search(r'.*\.(.*)\..*', file)
    global g_FileDate
    g_FileDate = dates.group(1)
    temp = count.copy()
    #将不在统计列表里的项列为非法访问
    for key in count:
        if key not in g_needlist:
            if 'illegality access' not in temp:
                temp['illegality access'] = [['%02d' % x, 0] for x in range(24)]
            for i in range(len(temp[key])):
                temp['illegality access'][i][1] += temp[key][i][1]
            del temp[key]
    return temp

#取得Y轴最大值(此函数感觉具有弄弄的c风格……应该可以优化)
def GetDictMax(count):
    max = 0
    for key in count:
       for each_list in count[key]:
            if each_list[1] > max:
                max = each_list[1]
    return max

#根据count制作图表
def MakeGraph(count, file):
    MultipleLocator.MAXTICKS = 100000
    fig = pl.figure(figsize=(15, 6))
    x = np.arange(0, 24, 1)
    y = []
    for key in count:
        y = [eachlist[1] for eachlist in count[key]]
        if key is "/update.xml":
            pl.plot(x, y, label = key, color = 'red')
        elif key is "/version.xml":
            pl.plot(x, y, label = key, color = 'blue')
        else:
            pl.plot(x, y, label = key)
    ax = pl.gca()

    max = GetDictMax(count)
    pl.ylim(0, max + g_Ystep - (max + g_Ystep) % g_Ystep)
    pl.xlim(0, np.max(x))

    pl.subplots_adjust(bottom = 0.15, right = 0.75)
    pl.grid()

    #设置x轴与y轴步长
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.yaxis.set_major_locator(MultipleLocator(g_Ystep))

    #设置图表标题
    pl.title(g_FileDate)

    #将图例放在图表之外
    pl.legend(bbox_to_anchor=(1.02, 1), loc=2, borderaxespad=0)
    fig.autofmt_xdate()
    #将图表保存为图片
    pl.savefig(g_FileDate + ".png")

#通过count生成prettytable
def MakeTable(count):
    names = []
    names.append("time")
    x = PrettyTable()
    x.add_column("time", range(0, 24))
    for key in count:
        list = [eachlist[1] for eachlist in count[key]]
        x.add_column(key, list)
    return x

#发送邮件
def SendMail(files):
    msg = MIMEMultipart('alternative')
    #将字典按照日期排序
    dic = sorted(g_MailDict.iteritems(), key = lambda x:x[0])
    html = ""
    for i in dic:
        #拼装html语句
        html += i[1]

        #插入图片
        image = MIMEImage(open("./" + i[0] + ".png", 'rb').read())
        image.add_header('Content-ID', i[0])
        msg.attach(image)
    #将html语句插入邮件内容
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    #将文件添加到附件
    for file in files:
        att = MIMEText(open(file, 'rb').read(), 'base64', 'utf-8')
        att["Content-Type"] = 'application/octet-stream'
        att["Content-Disposition"] = 'attachment; filename='+ file
        msg.attach(att)

    #此处两行写法很奇怪,为了群发才如此写
    strTo = ["test@gmail.com"]
    msg['to'] = ','.join(strTo)
    msg['from'] = '*****@gmail.com'
    subject = u"从" + dic[0][0] + u"至" + dic[-1][0] + u"的tomcat访问统计"
    msg['subject'] = subject

    try:
        server = smtplib.SMTP()
        server.connect('smtp.gmail.com')
        server.login('****@gmail.com', '*******')
        server.sendmail(msg['from'], strTo, msg.as_string())
        server.quit()
        print 'success'
    except Exception, e:
        print str(e)

#将prettytable转换成body内容
def MakeText(table):
    global g_MailDict
    global g_body
    text = g_FileDate + " tomcat access:"
    html = g_body % (text, table.get_html_string(attributes={"border":"1"}), g_FileDate)
    g_MailDict[g_FileDate] = html

if __name__ == "__main__":
    files = GetFileNames()
    for file in files:
        if ".DS_Store" in file:
            continue
        count = Dealwith(file)
        table = MakeTable(count)
        MakeGraph(count, file)
        MakeText(table)
    SendMail(files)
