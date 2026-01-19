# gr-rds-web-radio

**gr-rds-web-radio** is a complete demonstration project combining **GNU Radio**,
**RDS decoding**, **ZMQ messaging**, and a **web-based interface** to visualize
FM broadcast radio data in real time.

<img width="1808" height="956" alt="Web interface" src="https://github.com/user-attachments/assets/2b12ce95-f8a2-437b-be1f-24b38b5b9336" />

<img width="1862" height="1182" alt="GNU Radio flowgraph" src="https://github.com/user-attachments/assets/5d9308df-0d0a-4324-8815-4a9895b18c86" />

---

## Goal

The goal of this repository is to provide a clear, minimal, and educational example of:

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
- RDS bitstream decoding (PI, PS, RT, groups, etc.)  
- Automatic station detection  
- ZMQ PUB sockets for data exchange  
- Flask-based web interface  
- Real-time scopes and constellation display  
- Clean separation between GNU Radio DSP and UI  

Two operating modes are provided:

- **DEMO**: offline processing of a recorded IQ file (no hardware required)  
- **LIVE**: real-time reception using an RTL-SDR dongle (frequency tuning)

---

## Repository layout

```
gr-rds-web-radio/
├── demo/
│   ├── radio_rds_zmq_DEMO.grc
│   └── server_zmq_rds_DEMO.py
├── live/
│   ├── radio_rds_zmq_LIVE.grc
│   └── server_zmq_rds_LIVE.py
└── README.md
```

---

## Requirements

### Software

- GNU Radio 3.10+
- Python 3.9+
- Flask
- pyzmq
- NumPy

### Hardware (LIVE mode only)

- RTL-SDR USB dongle
- FM broadcast antenna

---

## DEMO mode (offline IQ file)

The `demo/` folder contains a fully working demonstration using a recorded IQ file.
No SDR hardware is required.

### Demo IQ file

Demo files (Raw IQ) can be downloaded here:

https://drive.google.com/file/d/1nZbhqOjQS7FJbejrz9Rja-n2DyCTEBk4/view?usp=sharing

Place the IQ file in the same folder as the demo `.grc` and server files
(or update the file path inside the GRC flowgraph).

---

### demo/radio_rds_zmq_DEMO.grc

GNU Radio Companion flowgraph implementing:

- FM broadcast demodulation
- RDS subcarrier extraction
- RDS decoding
- ZMQ outputs (JSON, scopes, constellation, etc.)

---

### demo/server_zmq_rds_DEMO.py

Flask web application that:

- Subscribes to ZMQ outputs from GNU Radio
- Displays decoded RDS information (PS, RT)
- Shows real-time signal visualizations
- Provides a lightweight web radio interface

---

### Running DEMO mode

1. Start GNU Radio:

```
gnuradio-companion demo/radio_rds_zmq_DEMO.grc
```

2. Start the web application:

```
python3 demo/server_zmq_rds_DEMO.py
```

3. Open your browser:

http://127.0.0.1:5000

---

## LIVE mode (RTL-SDR real-time reception)

The `live/` folder contains the real-time version of the project.
It requires an **RTL-SDR USB dongle** connected to the computer.

---

### live/radio_rds_zmq_LIVE.grc

GNU Radio Companion flowgraph implementing:

- Live FM broadcast reception using an RTL-SDR source
- Real-time FM demodulation
- RDS extraction and decoding
- ZMQ outputs identical to the DEMO version

In LIVE mode, the **center frequency can be changed dynamically**, allowing
real-time tuning across the FM broadcast band.

---

### live/server_zmq_rds_LIVE.py

Flask web application that:

- Subscribes to ZMQ outputs from the live GNU Radio flowgraph
- Displays decoded RDS information (PS, RT)
- Allows real-time station browsing
- Shows live signal visualizations

---

### Automatic station detection

In LIVE mode, station identification is performed **automatically**.

The RDS decoder continuously analyzes the received bitstream and detects the
**station PI code using autocorrelation techniques**.
This allows the system to:

- Detect the presence of a valid RDS signal
- Identify stations without prior knowledge
- Associate decoded PS/RT data with the currently tuned frequency

---

### Running LIVE mode

1. Connect the RTL-SDR dongle and antenna

2. Start GNU Radio:

```
gnuradio-companion live/radio_rds_zmq_LIVE.grc
```

3. Start the web application:

```
python3 live/server_zmq_rds_LIVE.py
```

4. Open your browser:

http://127.0.0.1:5000

---

## License

MIT License

---

## Author

Thomas Lavarenne  
https://github.com/tlavarenne
