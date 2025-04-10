docker build -f Dockerfile . -t api
docker run -d --rm -p 8000:8000 --name api --env-file .env api

# docker run --rm -it --entrypoint bash api
# docker exec -it api bash
# python -m tests.email
