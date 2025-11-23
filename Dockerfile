# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for pyodbc (MSSQL driver)
# python:3.11-slim-bullseye is Debian-based, so use apt.
RUN apt-get update && apt-get install -y \
    unixodbc-dev \
    gcc \
    # Clean up apt cache to keep image size small
    && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Disables the cache, which reduces the image size.
# --trusted-host pypi.python.org: Can help in environments with network issues.
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# --- DEBUG: List all copied files to verify contents ---
RUN ls -R /app

# Install module-specific dependencies
RUN for d in /app/modules/*/ ; do \
      if [ -f "${d}requirements.txt" ]; then \
        echo ">>> Installing dependencies for $(basename ${d})"; \
        pip install --no-cache-dir --trusted-host pypi.python.org -r "${d}requirements.txt"; \
      fi; \
    done

# Expose port 8000 to allow external traffic to the container
EXPOSE 8000

# Define the command to run your app using uvicorn
# --host 0.0.0.0 makes the server accessible from outside the container.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
