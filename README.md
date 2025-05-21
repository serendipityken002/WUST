### 快速启动
1. 运行串口服务器和数据库服务器
```bash
python server.py
python sb_test.py
```

2. 运行后端
```bash
python back.py
```

### 明确项目模块职责划分

1 后端
- 发送所有需要连接的串口给串口服务器，让其创建串口对象
- 接收前端JSON命令，将其解析为modbus帧，存入发送队列
- 将发送队列给串口服务器，串口服务器处理后会返回设备信息的modbus帧
- 接收串口服务器返回的modbus帧，存入接收队列，最后依次解析为JSON格式

2 串口服务器
- 接收后端提供的串口名、波特率等信息，创建串口对象
- 编写串口处理类和串口管理类对串口设备进行实际操作，包括提供串口数据接收、发送、关闭接口
- 根据{串口名: 串口对象}字典，提供串口名和modbus帧即可发送数据

3 数据库
- 只负责存储配置信息和设备实际数据
- 不需要把串口信息存储到数据库中

### 代码结构
`back.py`：这里主要讲解后端部分的代码，采用类将其封装，不再依赖全局变量。
## 概述

本项目旨在提供一个完整的解决方案，用于与远程服务器进行通信并处理来自RESTful API的数据更新。它通过TCP协议与特定的服务器建立连接，并使用HTTP长轮询机制从RESTful API中获取实时更新。整个应用设计为高度模块化，每个模块负责不同的功能，以确保代码清晰、易于维护和扩展。

## 项目结构

### 主要模块

1. **ConfigLoader** - 配置加载器
2. **TCPClient** - TCP客户端
3. **RestAPIClient** - RESTful API客户端
4. **ModbusHelper** - Modbus助手
5. **DeviceManager** - 设备管理器
6. **Application** - 应用主类

### 各模块作用

#### ConfigLoader
**作用**: 读取配置文件，静态方法，通过类名直接调用。

#### TCPClient

**作用**: 实现与指定服务器的TCP连接，支持发送和接收数据。对于每个TCP对象，都有自己的ip、队列、线程对象作为参数传入，避免了之前全局变量的使用。
- 数据发送和接收部分不变，通过JSON格式化数据并存入队列中。
- 发送和接收线程负责不断读取对象队列中的数据，不断与目标TCP服务器进行数据交换。

#### RestAPIClient

**作用**: 与RESTful API进行交互，包括连接测试、发送数据以及通过长轮询机制获取实时更新。
- 通过创建会话对象来管理与RESTful API的连接，之后就是基于post、put、get等方法进行数据的发送和接收。

#### ModbusHelper

**作用**: 处理Modbus相关的功能，目前有计算CRC校验码和格式化Modbus请求。
- 使用了静态方法装饰器`@staticmethod`，使得这些方法可以在不实例化类的情况下直接调用。在`java`中叫做类方法，直接通过类名调用。如：
```python
ModbusHelper.calculate_crc(data) # 不需要实例化
```
- 当然，这些方法其实也可以直接作为函数存在，但为了保持一致，并且在未来可能会添加更多的Modbus相关功能，所以将其封装在一个类中。


#### DeviceManager

**作用**: 管理设备通信和数据处理，包括初始化串口、发送Modbus请求以及解析接收到的所有数据，负责调用上述模块来实现实际的数据交换。
- 初始化串口：读取配置文件的串口信息，并调用传过来的tcp对象与串口服务器进行通信，这一步告诉串口服务器需要初始化哪些串口。
- 发送modbus请求：依旧是读取JSON文件，并调用串口服务器对象的发送方法，将其解析为modbus帧，存入发送队列。
- 解析数据：从接收队列获取完整的JSON内容，将其通过解析函数解析为真实数据并发给RESTful API（给数据库）。

#### Application

**作用**: 整个应用的入口点，负责协调各个组件的工作。创建各个对象并传给刚刚的设备管理器对象进行调用。
- 初始化config，创建TCP对象、RESTful API对象和设备管理器对象。
- 接着按顺序执行流程：
  - 连接服务器和RESTful API
  - 初始化串口
  - 从JSON文件中读取数据并不断发送给串口服务器并解析接收到的数据。
  - 每次解析完的数据都会发给RESTful API存入数据库中。


### 接口文档

1 前端发送的json请求
请求格式：
```python
json_data = {
    'serial': 'COM 50',
    'slave_adress': '1',
    'function_code': '3',
    'start_address': '2',
    'quantity': '4',
}
```

2 后端发送数据给串口服务器

2.1 发送所有需要连接的串口给串口服务器，让其创建串口对象
数据格式如下：
```bash
[
{"name": "COM44", "description": "WCH USB-SERIAL Ch A", "baudrate": 9600, "timeout": 1, "db_id": 1}, 
{"name": "COM45", "description": "WCH USB-SERIAL Ch C", "baudrate": 9600, "timeout": 1, "db_id": 2}, 
{"name": "COM50", "description": "WCH USB-SERIAL Ch D", "baudrate": 9600, "timeout": 1, "db_id": 3}
]
```

2.2 接收前端JSON命令，将其解析为modbus帧，存入发送队列后即可发给后端服务器
数据格式如下：
```python
data = json.dumps({
    'serial': serial,
    'request': request,
    'time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
})
```

2.3 接收串口服务器返回的modbus帧，按字节存入接收队列
串口服务器返回数据：
```python
data = json.dumps({
    "serial": serial,
    "request": request,
    "response": response,
    "time": time
})
```