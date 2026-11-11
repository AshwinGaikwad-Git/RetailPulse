FROM python:3.12-slim
WORKDIR /app
COPY requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt
COPY src ./src
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
COPY streamlit_app.py ./
RUN mkdir -p dataset
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
