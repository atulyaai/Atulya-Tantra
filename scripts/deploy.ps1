Param(
  [ValidateSet('build','push','deploy','all','help')]
  [string]$Command = 'all',
  [string]$Tag = 'latest',
  [string]$Registry = ''
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-ErrorMsg($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Build-Image {
  Write-Info "Building Docker image..."
  docker build -t atulya-tantra:$Tag .
}

function Push-Image {
  if ($Registry -ne '') {
    docker tag atulya-tantra:$Tag $Registry/atulya-tantra:$Tag
    docker push $Registry/atulya-tantra:$Tag
  } else {
    Write-ErrorMsg "Registry not provided for push"
  }
}

function Deploy-K8s {
  Write-Info "Deploying to Kubernetes..."
  kubectl apply -f k8s/namespace.yaml
  kubectl apply -f k8s/configmap.yaml
  kubectl apply -f k8s/secrets.yaml
  kubectl apply -f k8s/pvc.yaml
  kubectl apply -f k8s/deployment.yaml
  kubectl apply -f k8s/service.yaml
  kubectl apply -f k8s/ingress.yaml
}

switch ($Command) {
  'build' { Build-Image }
  'push' { Push-Image }
  'deploy' { Deploy-K8s }
  'help' { Write-Host "Usage: .\scripts\deploy.ps1 [build|push|deploy|all] -Tag vX -Registry your.registry" }
  default {
    Build-Image
    if ($Registry -ne '') { Push-Image }
    Deploy-K8s
  }
}


