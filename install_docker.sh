#!/bin/bash
# Docker Installation Script for Ubuntu 24.04
# Run this script with: bash install_docker.sh

set -e

echo "==================================="
echo "Docker Installation for Ubuntu 24.04"
echo "==================================="
echo ""

# Update package index
echo "Step 1: Updating package index..."
sudo apt-get update

# Install prerequisites
echo "Step 2: Installing prerequisites..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
echo "Step 3: Adding Docker's GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo "Step 4: Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index again
echo "Step 5: Updating package index with Docker repository..."
sudo apt-get update

# Install Docker Engine, CLI, and Docker Compose
echo "Step 6: Installing Docker Engine and Docker Compose..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker service
echo "Step 7: Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group (optional - allows running docker without sudo)
echo "Step 8: Adding current user to docker group..."
sudo usermod -aG docker $USER

echo ""
echo "==================================="
echo "Docker Installation Complete!"
echo "==================================="
echo ""
echo "Docker version:"
sudo docker --version
echo ""
echo "Docker Compose version:"
sudo docker compose version
echo ""
echo "IMPORTANT: You may need to log out and log back in for group changes to take effect."
echo "Or run: newgrp docker"
echo ""
echo "Test Docker with: sudo docker run hello-world"
echo ""
