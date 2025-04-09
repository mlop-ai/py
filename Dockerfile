# FROM python:3
FROM condaforge/miniforge3
ADD python python
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt --root-user-action ignore

# EXPOSE 8080
ENTRYPOINT ["python3", "python/main.py"]
