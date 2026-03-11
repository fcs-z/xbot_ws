# xbot
- 若github失败，可使用git clone https://gitee.com/fcsz/xbot.git
- 以下所有命令为gazebo仿真环境，若在实体机器人运行取消所有命令后缀 _gazebo
## 0 运行环境和安装依赖
```
ubuntu2204
ros2--humble
```
```
pip3 install vosk sounddevice numpy pypinyin

sudo apt install -y mpg123 portaudio19-dev python3-dev
pip3 install --upgrade rclpy pyaudio edge-tts vosk requests sounddevice
```
## 一、建图（xbot_slam）
### 1.1 建图
```
ros2 launch xbot_slam slam_gazebo.launch.py     
```
可将gazebo创建的地图保存至xbot_slam/worlds，再修改slam_gazebo.launch.py中world_file
### 1.2 键盘控制
```
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```
### 1.3 保存地图
```
ros2 run nav2_map_server map_saver_cli -f map_test
```  
运行1.3命令后会在当前运行目录下生成map_test.pgm和map_test.yaml文件，将2个文件移至xbot_ws/src/xbot_navigation2/maps下
## 二、导航（xbot_navigation2）
### 2.1 导航
```
ros2 launch xbot_navigation2 navigation_gazebo.launch.py
```
### 2.2 生成代价地图和导航目标点
在打开的rviz2中哦重定位，设置目标点
## 三、人脸跟随（xbot_face_follower）
```
ros2 launch xbot_face_follower face_follower_gazebo.launch.py
```
## 四、人体跟随（xbot_person_follower）
```
ros2 launch xbot_person_follower person_follower_gazebo.launch.py
```
## 五、巡线（xbot_line_walking）
```
ros2 launch xbot_line_walking line_walking_gazebo.launch.py
```
## 六、语音控制（xbot_voice_control）
src/xbot_voice_control/xbot_voice_control/voice_control.py中19行MODEL_PATH修改路径
```
ros2 launch xbot_voice_control voice_control_gazebo.launch.py
```
## 七、语音交互（xbot_voice_communication）
src/xbot_voice_communication/xbot_voice_communication/asr.py中24行model_path修改路径

deepseek api key 可自行官网获得：https://platform.deepseek.com/api_keys，付费

src/xbot_voice_communication/models太大，暂存至qq群
```
export DEEPSEEK_API_KEY=sk-055e90b5eb6240deb9ee9f8a266737a5
ros2 run xbot_voice_communication voice_communication
```