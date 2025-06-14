#!/bin/bash
# GCP disk space monitoring and alerting script

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"medialens"}
THRESHOLD_PERCENT=80
INSTANCE_NAME=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/name" -H "Metadata-Flavor: Google" 2>/dev/null)
ZONE=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/zone" -H "Metadata-Flavor: Google" 2>/dev/null | cut -d/ -f4)

# Function to check disk usage
check_disk_usage() {
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    echo "Current disk usage: ${usage}%"
    
    if [ "$usage" -gt "$THRESHOLD_PERCENT" ]; then
        echo "ALERT: Disk usage is ${usage}%, exceeding threshold of ${THRESHOLD_PERCENT}%"
        
        # Log to GCP Logging
        gcloud logging write media-lens-disk-alert \
            "{\"severity\":\"ERROR\",\"message\":\"Disk usage critical: ${usage}%\",\"instance\":\"${INSTANCE_NAME}\",\"zone\":\"${ZONE}\"}" \
            --severity=ERROR 2>/dev/null || true
            
        # Clean up Docker resources
        cleanup_docker_resources
        
        return 1
    fi
    return 0
}

# Function to cleanup Docker resources
cleanup_docker_resources() {
    echo "Cleaning up Docker resources..."
    
    # Remove unused containers
    docker container prune -f 2>/dev/null || true
    
    # Remove unused images
    docker image prune -f 2>/dev/null || true
    
    # Remove unused volumes
    docker volume prune -f 2>/dev/null || true
    
    # Remove build cache
    docker builder prune -f 2>/dev/null || true
    
    echo "Docker cleanup completed"
}

# Function to setup monitoring
setup_monitoring() {
    # Create a systemd service for continuous monitoring
    cat > /etc/systemd/system/disk-monitor.service << EOF
[Unit]
Description=Disk Space Monitor
After=network.target

[Service]
Type=oneshot
ExecStart=/app/monitor-disk-space.sh
User=root

[Install]
WantedBy=multi-user.target
EOF

    # Create a timer to run every 5 minutes
    cat > /etc/systemd/system/disk-monitor.timer << EOF
[Unit]
Description=Run Disk Space Monitor every 5 minutes
Requires=disk-monitor.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start the timer
    systemctl daemon-reload
    systemctl enable disk-monitor.timer
    systemctl start disk-monitor.timer
    
    echo "Disk monitoring setup completed"
}

# Main execution
case "${1:-check}" in
    "check")
        check_disk_usage
        ;;
    "cleanup")
        cleanup_docker_resources
        ;;
    "setup")
        setup_monitoring
        ;;
    "status")
        df -h /
        docker system df 2>/dev/null || true
        ;;
    *)
        echo "Usage: $0 {check|cleanup|setup|status}"
        exit 1
        ;;
esac