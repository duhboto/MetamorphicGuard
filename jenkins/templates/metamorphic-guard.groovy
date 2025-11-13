// Metamorphic Guard Evaluation Template for Jenkins
//
// Usage:
//   1. Create a new Jenkins Pipeline job
//   2. Copy this script into the Pipeline script
//   3. Configure environment variables in Jenkins
//   4. Customize task, baseline, and candidate paths

pipeline {
    agent any
    
    environment {
        MG_TASK_NAME = 'top_k'
        MG_BASELINE_PATH = 'baseline.py'
        MG_CANDIDATE_PATH = 'candidate.py'
        MG_N = '400'
        MG_MIN_DELTA = '0.02'
        MG_MIN_PASS_RATE = '0.80'
        // Optional: For LLM evaluations
        // OPENAI_API_KEY = credentials('openai-api-key')
        // ANTHROPIC_API_KEY = credentials('anthropic-api-key')
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Setup') {
            steps {
                sh '''
                    python3 -m pip install --upgrade pip
                    pip install metamorphic-guard
                    pip install -r requirements.txt || true
                '''
            }
        }
        
        stage('Metamorphic Guard Evaluation') {
            steps {
                sh '''
                    metamorphic-guard evaluate \
                        --task ${MG_TASK_NAME} \
                        --baseline ${MG_BASELINE_PATH} \
                        --candidate ${MG_CANDIDATE_PATH} \
                        --n ${MG_N} \
                        --min-delta ${MG_MIN_DELTA} \
                        --min-pass-rate ${MG_MIN_PASS_RATE} \
                        --report-dir reports \
                        --html-report reports/report.html \
                        --junit-report reports/junit.xml
                '''
            }
        }
        
        stage('Publish Results') {
            steps {
                junit 'reports/junit.xml'
                publishHTML([
                    reportDir: 'reports',
                    reportFiles: 'report.html',
                    reportName: 'Metamorphic Guard Report'
                ])
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'reports/**', fingerprint: true
        }
        success {
            echo 'Metamorphic Guard evaluation passed'
        }
        failure {
            echo 'Metamorphic Guard evaluation failed'
        }
    }
}

// Alternative: Declarative Pipeline with parameters
pipeline {
    agent any
    
    parameters {
        string(name: 'TASK_NAME', defaultValue: 'top_k', description: 'Task name')
        string(name: 'BASELINE_PATH', defaultValue: 'baseline.py', description: 'Baseline implementation path')
        string(name: 'CANDIDATE_PATH', defaultValue: 'candidate.py', description: 'Candidate implementation path')
        string(name: 'N', defaultValue: '400', description: 'Number of test cases')
    }
    
    stages {
        stage('Evaluate') {
            steps {
                sh '''
                    pip install metamorphic-guard
                    metamorphic-guard evaluate \
                        --task ${TASK_NAME} \
                        --baseline ${BASELINE_PATH} \
                        --candidate ${CANDIDATE_PATH} \
                        --n ${N} \
                        --report-dir reports
                '''
            }
        }
    }
}

