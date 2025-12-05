from flask import Flask, request, jsonify
import smtplib
from email.message import EmailMessage
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/send-pdf', methods=['POST'])
def send_pdf():
    data = request.get_json()
    user_email = data.get('email')

    if not user_email:
        return jsonify({'message': 'Email is required!'}), 400

    try:
        msg = EmailMessage()
        msg['Subject'] = 'Ready to Dive Deeper PDF'
        msg['From'] = 'your-email@example.com'   # Your sender email
        msg['To'] = user_email
        msg.set_content('Here is the PDF you requested.')

        with open('ReadyToDiveDeeper.pdf', 'rb') as pdf_file:
            msg.add_attachment(pdf_file.read(), maintype='application', subtype='pdf', filename='ReadyToDiveDeeper.pdf')

        # Set your SMTP server details here (replace with actual)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login('teesting7879@gmail.com', 'meyj vfsj fnak sczz')
            smtp.send_message(msg)

        return jsonify({'message': 'PDF sent successfully!'}), 200
    except Exception as e:
        return jsonify({'message': 'Failed to send email.', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
