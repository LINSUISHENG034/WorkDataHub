pypi 仓库使用说明

使用之前首先需要验证本机到我们的服务网络（30.16.105.251）端口 8445 是否已开通，网络是通的才可以正常使用，不然会有timeout的报错

如何查看python的包信息
我们的仓库不是一个镜像，所以无法使用文件路径的方式去查看仓库里面的所有包信息，只能精准的查看某个包的信息

可以访问如下地址查看包信息  http://maven.paic.com.cn:8445/repository/pypi/simple/你的包名/

例如： http://maven.paic.com.cn:8445/repository/pypi/simple/pyspark/

windows 本地修改 pip
根据自己得目录修改 pip.ini 文件中的地址如下：

D:\Users\xxxxx\AppData\Roaming\pip

修改 pip.ini

[global]
index-url=http://maven.paic.com.cn:8445/repository/pypi/simple/
trusted-host=maven.paic.com.cn

linux
pip install 的配置
mkdir ~/.pip
cd ~/.pip
cat >pip.conf<<EOF
[global]
timeout = 10
index-url=http://maven.paic.com.cn:8445/repository/pypi/simple/
extra-index-url=http://maven.paic.com.cn:8445/repository/pypi/simple/
[install]
trusted-host=maven.paic.com.cn
EOF

使用
pip install xxx 安装指定的包最新版本

pip install xxx==version 安装指定包的指定版本

pip list 查看已经安装的包列表

pip uninstall xxx==version 卸载指定的包

pip install <package_name> --index-url=http://maven.paic.com.cn:8445/repository/pypi/simple/ --trusted-host maven.paic.com.cn 指定仓库地址安装