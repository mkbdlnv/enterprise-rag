// CI/CD for the enterprise RAG service.
//
// Every commit to main (polled every 2 minutes): lint + unit tests in a
// throw-away test container -> retrieval evaluation (Recall@k, MRR) -> runtime
// image -> optional push -> deploy to the test server with health-check gate and
// automatic rollback.
//
// The agent only needs git and the docker CLI: Python, pytest and ruff live in
// the test image, so the build is the same on any Jenkins node.

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
        timeout(time: 20, unit: 'MINUTES')
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    environment {
        IMAGE = 'enterprise-rag'
        DEPLOY_PORT = '8091'
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    env.TAG = sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()
                    currentBuild.description = "commit ${env.TAG}"
                }
                sh 'git log -1 --format="%h %an: %s"'
            }
        }

        stage('Build test image') {
            steps {
                sh 'docker build --target test -t $IMAGE:test-$TAG .'
            }
        }

        stage('Lint') {
            steps {
                sh 'docker run --rm $IMAGE:test-$TAG ruff check .'
            }
        }

        stage('Unit tests') {
            steps {
                sh '''
                    rm -rf reports && mkdir -p reports
                    docker run --name rag-test-$BUILD_NUMBER $IMAGE:test-$TAG \
                        pytest --junitxml=/tmp/reports/junit.xml \
                               --cov --cov-report=term --cov-report=xml:/tmp/reports/coverage.xml
                '''
            }
            post {
                always {
                    sh 'docker cp rag-test-$BUILD_NUMBER:/tmp/reports/. reports/ || true'
                    sh 'docker rm -f rag-test-$BUILD_NUMBER || true'
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                }
            }
        }

        stage('Evaluate retrieval') {
            steps {
                sh 'docker run --rm $IMAGE:test-$TAG python -m ragsearch.evaluate --k 3 > reports/eval.json'
                sh 'cat reports/eval.json'
                archiveArtifacts artifacts: 'reports/*', fingerprint: true
            }
        }

        stage('Build image') {
            steps {
                sh '''
                    docker build --target runtime \
                        --build-arg GIT_REVISION=$TAG \
                        -t $IMAGE:$TAG -t $IMAGE:latest .
                    docker image ls $IMAGE
                '''
            }
        }

        stage('Push image') {
            // Optional: set PUSH_IMAGE=true and add a "registry" username/password
            // credential (Docker Hub or GHCR token) in Jenkins.
            when { environment name: 'PUSH_IMAGE', value: 'true' }
            steps {
                withCredentials([usernamePassword(credentialsId: 'registry',
                        usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
                    sh '''
                        echo "$REG_PASS" | docker login ${REGISTRY:-docker.io} -u "$REG_USER" --password-stdin
                        docker tag $IMAGE:$TAG ${REGISTRY:-docker.io}/$REG_USER/$IMAGE:$TAG
                        docker push ${REGISTRY:-docker.io}/$REG_USER/$IMAGE:$TAG
                        docker logout ${REGISTRY:-docker.io}
                    '''
                }
            }
        }

        stage('Deploy') {
            when { expression { env.GIT_BRANCH in ['origin/main', 'main'] } }
            steps {
                withCredentials([string(credentialsId: 'llm-api-key', variable: 'LLM_API_KEY')]) {
                    sh 'bash scripts/deploy.sh $IMAGE:$TAG $DEPLOY_PORT'
                }
            }
        }

        stage('Smoke test') {
            when { expression { env.GIT_BRANCH in ['origin/main', 'main'] } }
            steps {
                sh 'EXPECT_REVISION=$TAG bash scripts/smoke.sh rag'
            }
        }
    }

    post {
        always {
            sh 'docker rmi $IMAGE:test-$TAG || true'
        }
        success {
            echo "Deployed ${env.IMAGE}:${env.TAG} -> https://rag.mkab.dev"
        }
    }
}
