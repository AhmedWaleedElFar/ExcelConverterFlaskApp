#!/usr/bin/env python
# coding: utf-8

# In[1]:


from flask import Flask, request, render_template_string, send_file, redirect, url_for
import pandas as pd
from io import BytesIO
import threading

#Setting up proper logging
import logging
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
#A secure secret key for the tool.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Configure logging
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

def is_valid_digit_number(CC_number):
    return len(CC_number) == 16

def is_valid_format(CC_number):
    first_two = CC_number[0:2]
    second_two = CC_number[2:4]
    third_two = CC_number[4:6]
    return first_two == second_two == third_two

def is_valid(CC_number):
    return is_valid_digit_number(CC_number) and is_valid_format(CC_number)

def mask_number(CC_number):
    if is_valid(CC_number):
        masked_number = CC_number[:6] + '*' * 10
        return masked_number
    else:
        return None

def process_file_1(file):
    df = pd.read_excel(file)
    df['CC_number'] = df['CC_number'].astype(str)
    df['first_validation'] = df['CC_number'].apply(lambda x: 1 if is_valid_digit_number(x) else 0)
    df['second_validation'] = df['CC_number'].apply(lambda x: 1 if is_valid_format(x) else 0)
    df['MaskedNumber'] = df['CC_number'].apply(lambda x: mask_number(x) if is_valid(x) else None)
    return df


def read_excel_file(file):
    """Read the Excel file into a DataFrame."""
    df = pd.read_excel(file)
    return df

def validate_columns(df):
    """Check if the required 'type' column exists in the DataFrame."""
    if 'type' not in df.columns:
        raise ValueError("The required 'type' column is missing in the uploaded file.")

def separate_debit_credit_data(df):
    """Separate the DataFrame into debit and credit data."""
    debit_data = df[df['type'] == 'd'].reset_index(drop=True)
    credit_data = df[df['type'] == 'c'].reset_index(drop=True)
    return debit_data, credit_data

def create_output_buffer(data, num_output_files):
    """Create an in-memory buffer from the given data."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        data.to_excel(writer, sheet_name=f'Part_{num_output_files}', index=False)
    buffer.seek(0)
    return buffer

def process_data(debit_data, credit_data, max_entries_per_file=10):
    """Process debit and credit data and return a list of output buffers."""
    output_buffers = []

    while not debit_data.empty and not credit_data.empty:
        output_df = pd.DataFrame()
        num_output_files = len(output_buffers) + 1

        for i in range(max_entries_per_file // 2):
            if debit_data.empty or credit_data.empty:
                break

            output_df = pd.concat([output_df, debit_data.iloc[:1], credit_data.iloc[:1]])
            debit_data = debit_data.iloc[1:].reset_index(drop=True)
            credit_data = credit_data.iloc[1:].reset_index(drop=True)

        output_buffers.append(create_output_buffer(output_df, num_output_files))

    if not debit_data.empty or not credit_data.empty:
        num_output_files = len(output_buffers) + 1
        leftover_df = pd.concat([debit_data, credit_data])
        output_buffers.append(create_output_buffer(leftover_df, num_output_files))

    return output_buffers

def combine_output_buffers(output_buffers):
    """Combine all output buffers into a single in-memory Excel file."""
    combined_output = BytesIO()
    with pd.ExcelWriter(combined_output, engine='xlsxwriter') as writer:
        for i, buffer in enumerate(output_buffers):
            buffer.seek(0)
            temp_df = pd.read_excel(buffer)
            temp_df.to_excel(writer, sheet_name=f'Part_{i+1}', index=False)
    combined_output.seek(0)
    return combined_output

def process_file_2(file):
    df = read_excel_file(file)
    validate_columns(df)
    debit_data, credit_data = separate_debit_credit_data(df)
    output_buffers = process_data(debit_data, credit_data)
    combined_output = combine_output_buffers(output_buffers)
    return combined_output



@app.route('/')
def index():
    return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Select Processing Option</title>
          <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
          <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
          <style>
            body {
                background-color: #f4f4f4;
                display: flex;
                height: 100vh;
                margin: 0;
            }
            .photo {
                flex: 2;
                background: url('{{ url_for('static', filename='background.png') }}') no-repeat center center;
                background-size: cover;
                height: 100%;
                width: 75%;
            }
            .options {
                flex: 1;
                background: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                
            }
            .options a {
                display: block;
                margin: 10px 0;
                padding: 10px 20px;
                background-color: #002B74;
                color: white;
                text-decoration: none;
                border-radius: 4px;
            }
            .options a:hover {
                background-color: #003DA6;
                transition: 0.4s;
            }
          </style>
        </head>
        <body>
          <div class="photo"></div>
          <div class="options">
            <h1 class="mb-4">Select Processing Option</h1>
            <a href="/option1" class="btn btn-primary">Process Credit Card Numbers</a>
            <a href="/option2" class="btn btn-primary">Process Debit and Credit Data</a>
          </div>
          <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
          <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js"></script>
          <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
        </body>
        </html>
    ''')




@app.route('/option1', methods=['GET', 'POST'])
def option1():
    return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Upload File for Option 1</title>
          <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
          <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                height: 100vh;
                background-color: #f4f4f4;
            }
            h1 {
                color: #333;
                margin-right: 20px;
            }
            .container {
                display: flex;
                flex-direction: row;
                justify-content: center;
                align-items: center;
                height: 100%
            }
            form {
                background: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            input[type="file"] {
                display: block;
                margin-bottom: 10px;
            }
            input[type="submit"] {
                background-color: #002B74;
                color: white;
                border: none;
                padding: 10px 20px;
                text-decoration: none;
                cursor: pointer;
                border-radius: 4px;
            }
            input[type="submit"]:hover {
                background-color: #003DA6;
                transition: 0.4s;
            }
            .extra-button {
                padding: 10px 20px;
                background-color: #002B74;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                width: 7%
            }
            .extra-button:hover {
                background-color: #003DA6;
                transition: 0.4s;
            }
          </style>
          <script>
            function validateForm() {
              var fileInput = document.getElementById('fileInput');
              if (fileInput.files.length === 0) {
                alert('No file chosen. Please select a file to upload.');
                return false; // Prevent form submission
              }
              return true; // Allow form submission
            }
          </script>
        </head>
        <body>
        <button class="extra-button align-items-center" onclick="window.location.href='/'">Back to home</button>
        <div class="container">
          <h1>Upload a File for Option 1</h1>
          <form action="/upload1" method="post" enctype="multipart/form-data" onsubmit="return validateForm()">
            <input type="file" id="fileInput" name="file" accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel">
            <input type="submit" value="Upload">
          </form>
        </div>
        </body>
        </html>
    ''')




@app.route('/option2', methods=['GET', 'POST'])
def option2():
    return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Upload File for Option 2</title>
          <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
          <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                height: 100vh;
                background-color: #f4f4f4;
            }
            h1 {
                color: #333;
                margin-right: 20px;
            }
            .container {
                display: flex;
                flex-direction: row;
                justify-content: center;
                align-items: center;
                height: 100%
            }
            form {
                background: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }
            input[type="file"] {
                display: block;
                margin-bottom: 10px;
            }
            input[type="submit"] {
                background-color: #002B74;
                color: white;
                border: none;
                padding: 10px 20px;
                text-decoration: none;
                cursor: pointer;
                border-radius: 4px;
            }
            input[type="submit"]:hover {
                background-color: #003DA6;
                transition: 0.4s;
            }
            .extra-button {
                padding: 10px 20px;
                background-color: #002B74;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                width: 7%;
            }
            .extra-button:hover {
                background-color: #003DA6;
                transition: 0.4s;
            }
          </style>
          <script>
            function validateForm() {
              var fileInput = document.getElementById('fileInput');
              if (fileInput.files.length === 0) {
                alert('No file chosen. Please select a file to upload.');
                return false; // Prevent form submission
              }
              return true; // Allow form submission
            }
          </script>
        </head>
        <body>
        <button class="extra-button" onclick="window.location.href='/'">Back to home</button>
        <div class="container">
          <h1>Upload a File for Option 2</h1>
          <form action="/upload2" method="post" enctype="multipart/form-data" onsubmit="return validateForm()">
            <input type="file" id="fileInput" name="file" accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel">
            <input type="submit" value="Upload">
          </form>
        </div>
        </body>
        </html>
    ''')



@app.route('/upload1', methods=['POST'])
def upload_file1():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    if file:
        processed_df = process_file_1(BytesIO(file.read()))
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            processed_df.to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, download_name='processed_file1.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return 'File upload failed'

@app.route('/upload2', methods=['POST'])
def upload_file2():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    if file:
        output = process_file_2(BytesIO(file.read()))
        return send_file(output, download_name='processed_file2.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return 'File upload failed'



def run_flask_app():
    app.run(debug=False, use_reloader=False)

flask_thread = threading.Thread(target=run_flask_app)
flask_thread.start()


# In[ ]:




