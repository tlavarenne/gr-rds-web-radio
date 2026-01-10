# gr-rds-web-radio

**gr-rds-web-radio** is a complete demonstration project combining **GNU Radio**,
**RDS decoding**, **ZMQ messaging**, and a **web-based interface** to visualize
FM broadcast radio data in real time.

Demo files (Raw IQ) to download at https://drive.google.com/file/d/1nZbhqOjQS7FJbejrz9Rja-n2DyCTEBk4/view?usp=sharing

The goal of this repository is to provide a clear, minimal, and educational
example of:
- FM broadcast reception
- RDS (Radio Data System) decoding
- Message and signal export via ZMQ
- Real-time visualization using a Flask web application

This project is suitable for:
- SDR experimentation
- Teaching digital communications / broadcast radio
- Demonstrations and labs (BTS, engineering schools, self-learning)

---

## Features

- FM broadcast receiver
- RDS bitstream decoding (PS, RT, groups, etc.)
- ZMQ PUB sockets for data exchange
- Flask-based web interface
- Real-time scopes and constellation display
- Clean separation between GNU Radio DSP and UI

---

## Demo directory

The demo/ folder contains a fully working demonstration.

### fm_rds_demo.grc

GNU Radio Companion flowgraph implementing:
- FM broadcast demodulation
- RDS extraction and decoding
- ZMQ outputs (JSON, scopes, constellation, etc.)

### server_zmq_rds_DEMO.py

Flask web application that:
- Subscribes to ZMQ outputs from GNU Radio
- Displays decoded RDS information (PS, RT)
- Shows real-time signal visualizations
- Provides a lightweight web radio interface

---

## Requirements

Software requirements:
- GNU Radio 3.10+
- Python 3.9+
- Flask
- pyzmq
- NumPy

---

## Running the demo
1. Download Demo Files at https://drive.google.com/file/d/1nZbhqOjQS7FJbejrz9Rja-n2DyCTEBk4/view?usp=sharing and put it in the same folder that the GRC and server files.

2. Start GNU Radio:
gnuradio-companion demo/fm_rds_demo.grc

3. Start the web application:
python3 demo/app.py

4. Open your browser:
http://127.0.0.1:5000

---

## Educational use

This repository is suitable for:
- SDR and radio communications courses
- FM/RDS protocol analysis
- GNU Radio teaching labs
- Demonstration and experimentation

---

## License

MIT License

---

## Author

Thomas Lavarenne  
https://github.com/tlavarenne
