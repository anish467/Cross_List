from flask import Flask, render_template, request, redirect, url_for
import os
import re
import pdfplumber
import psycopg2
import psycopg2.extras
import pandas as pd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

hostname = 'localhost'
database = 'SDLproject'
username = 'postgres'
pwd = 'Air@8888'
port_id = 5432

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def upload_form():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        process_pdf(file_path)
        return redirect(url_for('upload_form', filename=filename))
    return redirect(request.url)

def process_pdf(file_path):
    try:
        conn = psycopg2.connect(
            host=hostname,
            user=username,
            dbname=database,
            password=pwd,
            port=port_id
        )
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        with pdfplumber.open(file_path) as pdf:
            num_pages = len(pdf.pages)
            goal = re.compile(r"0801[A-Z][A-Z]\d{6}")
            lateral = re.compile(r"0801[A-Z][A-Z]\d{3}[A-Z]\d{2}")
            sem1 = re.compile(r"First Semester")
            sem2 = re.compile(r"Second Semester")
            sem3 = re.compile(r"IIIrd Semester")
            sem4 = re.compile(r"IVth Semester")

            cur.execute("""TRUNCATE student;""")
            cur.execute("""DROP TABLE IF EXISTS final;""")

            for i in range(num_pages):
                page = pdf.pages[i]
                text = page.extract_text()
                sem = 'ktsem1'
                if (sem2.search(text)):
                    sem = 'ktsem2'
                if (sem3.search(text)):
                    sem = 'ktsem3'
                if (sem4.search(text)):
                    sem = 'ktsem4'
                for line in text.split('\n'):
                    if goal.search(line):
                        temp = goal.search(line)
                        comma_count = line.count(',')
                        insert_statement = f"""INSERT INTO student (roll_no,{sem}) VALUES (%s,%s)"""
                        variables = (temp.group(), comma_count + 1)
                        cur.execute(insert_statement, variables)
                    if lateral.search(line):
                        temp = lateral.search(line)
                        comma_count = line.count(',')
                        insert_statement = f"""INSERT INTO student (roll_no,{sem}) VALUES (%s,%s)"""
                        variables = (temp.group(), comma_count + 1)
                        cur.execute(insert_statement, variables)
        #make final table
        cur.execute("""create table final as (
                            SELECT 
                            roll_no,
                            SUM(ktsem1) AS ktsem1,
                            SUM(ktsem2) AS ktsem2,
                            SUM(ktsem3) AS ktsem3,
                            SUM(ktsem4) AS ktsem4
                        FROM 
                            student
                        GROUP BY 
                            roll_no
                        ORDER BY
                            roll_no
                        )""")
        cur.execute("""ALTER TABLE final
                       ADD result VARCHAR(20) DEFAULT 'Can Go To Next Sem' """)
        cur.execute("""SELECT * FROM final""")
        for record in cur.fetchall():
            sum = record['ktsem1']+record['ktsem2']+record['ktsem3']+record['ktsem4']
            vari = str(record['roll_no'])
            if sum>5:
                update_entry = f"""UPDATE final
                                   SET result = 'SEM BACK' 
                                   WHERE roll_no = %s """
                cur.execute(update_entry,(vari,))
        cur.execute("""CREATE TABLE List AS (SELECT * FROM final ORDER BY roll_no)""")
        cur.execute("""DROP TABLE final""")
        conn.commit()
        #To download the file
        cur = conn.cursor()
        output_file = "output.csv"
        copy_query = f"COPY List TO STDOUT WITH CSV HEADER"
        with open(output_file,"w") as f:
            cur.copy_expert(copy_query,f)
        cur.close()
    except Exception as error:
        print(error)
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
