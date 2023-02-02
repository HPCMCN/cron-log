按照cron规则, 定时滚动日志文件.
使用方式:
* 创建文件: logging.json
```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "verbose": {
      "format": "[%(levelname).4s] %(asctime)s P_%(process)d_T_%(thread)d <%(module)s:%(lineno)d>: %(message)s"
    },
    "simple": {
      "format": "[%(levelname).4s] %(asctime)s P_%(process)d_T_%(thread)d <%(module)s:%(lineno)d>: %(message)s"
    }
  },
  "handlers": {
    "console": {
      "level": "DEBUG",
      "stream": "ext://sys.stdout",
      "class": "logging.StreamHandler",
      "formatter": "simple"
    },
    "file": {
      "level": "INFO",
      "class": "cron_log.handlers.CronRotatingFileHandler",
      "filename": "logs/running.log",
      "maxBytes": 314572800,
      "crontab": "*/1 * * * *",
      "keepBackup": "1m",
      "formatter": "verbose"
    }
  },
  "loggers": {
    "root": {
      "level": "INFO",
      "handlers": [
        "console",
        "file"
      ]
    }
  }
}
```
  * maxBytes: 超过maxBytes字节, 将会进行强制日志滚动, 没有配置则不进行处理
  * crontab: `1 * * * *`, 表示每天一点进行日志滚动, 没有配置则不进行处理
  * keepBackup: `7d`, 表示日志文件, 将会保留7天量, 否则进行清理, 没有配置则不进行处理
    * d: 表示天
    * h: 表示小时
    * m: 表示分钟

* logging使用
```python
import json
import logging.config

logging.config.dictConfig(json.load(open("logging.json")))

logging.info("test file")
```