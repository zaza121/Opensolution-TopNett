FROM odoo:16.0
USER root
RUN apt-get update -y
RUN apt-get install -y python3-paramiko
RUN pip install google-auth