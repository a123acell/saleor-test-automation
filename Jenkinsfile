// Jenkins 声明式流水线 —— 只负责「编排」，命令统一走 ci/pipeline.py
//
// 为什么命令不内联进 Jenkinsfile：
// 如果这里手写 pytest / jmeter 命令，本地想验证流水线就得再抄一遍，
// 两处必然漂移——改了脚本忘了改编排，CI 会静默地跑旧命令或漏跑阶段。
// 因此每个 stage 都调用 `python ci/pipeline.py <id>`；本地
// `python ci/pipeline.py all` 即可复现整条流水线。
// Jenkinsfile 编排的阶段与 ci/pipeline.py 的 STAGES 是否一致，
// 由 scripts/selfcheck.py 第 18 项机械校验。

// 跨平台执行：Linux 代理用 sh，Windows 代理用 bat，参数完全一致。
def runStage(String stage) {
    if (isUnix()) {
        sh "python ci/pipeline.py ${stage}"
    } else {
        bat "python ci/pipeline.py ${stage}"
    }
}

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '20'))
    }

    parameters {
        string(name: 'PERF_THREADS', defaultValue: '5', description: '性能冒烟并发数（单档短时验证链路）')
        string(name: 'PERF_DURATION', defaultValue: '15', description: '性能冒烟持续秒数')
    }

    environment {
        PYTHONIOENCODING = 'utf-8'
        PERF_THREADS = "${params.PERF_THREADS}"
        PERF_DURATION = "${params.PERF_DURATION}"
        // 若代理机未把 jmeter / allure 加入 PATH，可在 Jenkins 全局环境变量里补：
        // JMETER_HOME = '/opt/apache-jmeter'        // 自动拼 bin/jmeter
        // JMETER_BIN  = '/opt/apache-jmeter/bin/jmeter'  // 优先级最高
        // ALLURE_BIN  = '/opt/allure/bin/allure'
    }

    stages {
        stage('环境与依赖检查') {
            steps { runStage('bootstrap') }
        }
        stage('工程自检') {
            steps { runStage('selfcheck') }
        }
        stage('用例收集') {
            steps { runStage('collect') }
        }
        stage('接口自动化') {
            steps { runStage('api') }
        }
        stage('UI 自动化') {
            steps { runStage('ui') }
        }
        stage('性能冒烟') {
            steps { runStage('perf') }
        }
    }

    post {
        always {
            // JUnit XML：失败用例在构建页直接可读
            junit allowEmptyResults: true, testResults: 'reports/*.xml'
            // Allure 报告：需安装 Allure Jenkins Plugin
            allure includeProperties: false, jdk: '', results: [[path: 'allure-results']]
            // 产物归档：JUnit 结果 + 性能冒烟 JTL 原始数据
            archiveArtifacts artifacts: 'reports/*.xml,perftests/results/ci/*.jtl',
                             allowEmptyArchive: true
        }
        failure {
            echo '流水线失败：按阶段定位——bootstrap 查环境、selfcheck 查工程质量、api/ui/perf 查用例与链路。'
        }
    }
}