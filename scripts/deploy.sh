#!/bin/bash

# Atulya Tantra - Production Deployment Script
# Version: 2.5.0

set -e

# Configuration
APP_NAME="atulya-tantra"
NAMESPACE="atulya-tantra"
DOCKER_REGISTRY="your-registry.com"
DOCKER_TAG="${1:-latest}"
ENVIRONMENT="${2:-production}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed"
        exit 1
    fi
    
    # Check if helm is installed
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi
    
    # Check kubectl connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Build and push Docker image
build_and_push_image() {
    log_info "Building and pushing Docker image..."
    
    # Build image
    docker build -t ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_TAG} .
    
    # Push image
    docker push ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_TAG}
    
    log_success "Docker image built and pushed: ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_TAG}"
}

# Deploy to Kubernetes
deploy_to_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    # Create namespace if it doesn't exist
    kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply ConfigMap
    kubectl apply -f k8s/configmap.yaml
    
    # Apply Secrets (update with actual values)
    log_warning "Please update k8s/secrets.yaml with actual secret values before deploying"
    kubectl apply -f k8s/secrets.yaml
    
    # Apply PVCs
    kubectl apply -f k8s/pvc.yaml
    
    # Apply Services
    kubectl apply -f k8s/service.yaml
    
    # Update deployment with new image
    sed "s|image: atulya-tantra:latest|image: ${DOCKER_REGISTRY}/${APP_NAME}:${DOCKER_TAG}|g" k8s/deployment.yaml | kubectl apply -f -
    
    # Apply Ingress
    kubectl apply -f k8s/ingress.yaml
    
    log_success "Kubernetes deployment completed"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Get pod name
    POD_NAME=$(kubectl get pods -n ${NAMESPACE} -l app=${APP_NAME} -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$POD_NAME" ]; then
        log_error "No pods found for ${APP_NAME}"
        exit 1
    fi
    
    # Run migrations
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- alembic upgrade head
    
    log_success "Database migrations completed"
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    # Wait for deployment to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/${APP_NAME}-app -n ${NAMESPACE}
    
    # Get service URL
    SERVICE_URL=$(kubectl get ingress ${APP_NAME}-ingress -n ${NAMESPACE} -o jsonpath='{.spec.rules[0].host}')
    
    if [ -z "$SERVICE_URL" ]; then
        log_warning "No ingress found, using port-forward for health check"
        kubectl port-forward -n ${NAMESPACE} service/${APP_NAME}-service 8080:80 &
        PORT_FORWARD_PID=$!
        sleep 5
        SERVICE_URL="localhost:8080"
    fi
    
    # Perform health check
    for i in {1..30}; do
        if curl -f http://${SERVICE_URL}/api/health &> /dev/null; then
            log_success "Health check passed"
            break
        fi
        
        if [ $i -eq 30 ]; then
            log_error "Health check failed after 30 attempts"
            exit 1
        fi
        
        log_info "Health check attempt $i/30 failed, retrying in 10 seconds..."
        sleep 10
    done
    
    # Clean up port-forward if used
    if [ ! -z "$PORT_FORWARD_PID" ]; then
        kill $PORT_FORWARD_PID
    fi
}

# Rollback deployment
rollback() {
    log_warning "Rolling back deployment..."
    
    # Rollback deployment
    kubectl rollout undo deployment/${APP_NAME}-app -n ${NAMESPACE}
    
    # Wait for rollback to complete
    kubectl rollout status deployment/${APP_NAME}-app -n ${NAMESPACE}
    
    log_success "Rollback completed"
}

# Cleanup old resources
cleanup() {
    log_info "Cleaning up old resources..."
    
    # Delete old replicas
    kubectl delete pods -n ${NAMESPACE} -l app=${APP_NAME} --field-selector=status.phase=Succeeded
    
    # Clean up old images (optional)
    # docker image prune -f
    
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting deployment of ${APP_NAME} to ${ENVIRONMENT} environment"
    
    # Check prerequisites
    check_prerequisites
    
    # Build and push image
    build_and_push_image
    
    # Deploy to Kubernetes
    deploy_to_kubernetes
    
    # Run migrations
    run_migrations
    
    # Health check
    health_check
    
    # Cleanup
    cleanup
    
    log_success "Deployment completed successfully!"
    log_info "Application is available at: http://${SERVICE_URL}"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "rollback")
        rollback
        ;;
    "health")
        health_check
        ;;
    "migrate")
        run_migrations
        ;;
    *)
        echo "Usage: $0 [deploy|rollback|health|migrate] [tag] [environment]"
        echo "  deploy   - Deploy the application (default)"
        echo "  rollback - Rollback to previous version"
        echo "  health   - Perform health check"
        echo "  migrate  - Run database migrations"
        echo "  tag      - Docker image tag (default: latest)"
        echo "  environment - Deployment environment (default: production)"
        exit 1
        ;;
esac
