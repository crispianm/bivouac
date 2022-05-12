FROM python:3.9.1
ADD . /bivouac
WORKDIR /bivouac
RUN pip install -r requirements.txt