# Stage 1: build the React app into static files (needs Node.js)
FROM node:22-alpine AS build
WORKDIR /app
# Install exact versions from package-lock.json; cached unless dependencies change.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve the built files with nginx (no Node.js in the final image)
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.inc /etc/nginx/security-headers.inc
COPY --from=build /app/dist /usr/share/nginx/html
