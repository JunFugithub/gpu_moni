node:
	mkdir node_exporter
	wget -O node_exporter/node_exporter.tar.gz https://github.com/prometheus/node_exporter/releases/download/v0.16.0/node_exporter-0.16.0.linux-amd64.tar.gz
	tar -xzf node_exporter/node_exporter.tar.gz -C node_exporter && mv node_exporter/*linux* node_exporter/nodeE

install: node
	install -d -m 777 /run/prometheus
	install -m 775 dcgm-exporter/dcgm-exporter /usr/local/bin/
	install -m 644 prometheus-dcgm.service /etc/systemd/system/

uninstall:
	rm -rf /run/prometheus
	rm -f /usr/local/bin/dcgm-exporter
	rm -f /etc/systemd/system/prometheus-dcgm.service
	rm -rf node_exporter

exporter:
	dcgm-exporter &
	node_exporter/nodeE/node_exporter --collector.textfile.directory=/run/prometheus &
