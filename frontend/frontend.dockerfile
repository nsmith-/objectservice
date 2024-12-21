# Use the official Node.js image as the base image
FROM node:23-alpine

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Install a simple HTTP server to serve the static files
RUN npm install -g serve

# Command to build and serve the app
# (we defer building to startup to acquire runtime environment variables)
CMD ["sh", "-c", "npm run build && serve -s build -l 5000"]