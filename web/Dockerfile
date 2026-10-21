# Stage 1: build the React app into static files (needs Node.js)
FROM node:22.23.3-alpine AS build
WORKDIR /app
# Install exact versions from package-lock.json; cached unless dependencies change.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Which copy this build is for: "prod" leaves out hobbies still under construction (src/modules/index.js).
ARG APP_ENV=prod
ENV VITE_APP_ENV=$APP_ENV
RUN npm run build

# Stage 2: serve the built files with nginx (no Node.js in the final image)
FROM nginx:1.27.5-alpine
# a template: ${HTTPS_PORT} is filled in when the container starts (the nginx image's own envsubst step)
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY security-headers.inc /etc/nginx/security-headers.inc
COPY --from=build /app/dist /usr/share/nginx/html
