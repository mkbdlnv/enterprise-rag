# Jenkins controller for the enterprise-rag pipeline, configured entirely as
# code: plugins from plugins.txt, users/credentials/job from casc.yaml. No
# setup wizard, nothing clicked by hand, so the server can be rebuilt from git.
FROM jenkins/jenkins:lts-jdk21

USER root
# Docker CLI + buildx only; builds run on the host daemon via the mounted socket.
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:29-cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
USER jenkins

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY casc.yaml /usr/share/jenkins/casc.yaml
ENV CASC_JENKINS_CONFIG=/usr/share/jenkins/casc.yaml \
    JAVA_OPTS="-Xmx384m -XX:+UseSerialGC -Djenkins.install.runSetupWizard=false"
