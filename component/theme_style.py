# component/theme_style.py

class PurpleTheme:
    """
    现代浅紫色主题样式表 (Light Purple Modern Theme)
    特点: 圆角, 柔和色调, 扁平化, 适当的半透明感
    """
    STYLE_SHEET = """
    /* 全局设置 */
    * {
        font-family: "Segoe UI", "Microsoft YaHei", PingFang SC, sans-serif;
        color: #333333; /*主要文字颜色: 深灰*/
    }

    /* 主窗口背景: 极淡的紫色 */
    QMainWindow {
        background-color: #F3E5F5; 
    }

    /* ——— 容器与分组框 ——— */
    /* 右侧控制面板区域的背景，假设在ui里有一个容器widget包着它们，如果没有也没关系，下面QGroupBox有背景色 */
    QWidget#controlPanelContainer {
         background-color: rgba(255, 255, 255, 0.8); /* 轻微半透明的白色背景 */
         border-top-left-radius: 20px;
         border-bottom-left-radius: 20px;
    }

    QGroupBox {
        background-color: #FFFFFF; /* 纯白背景 */
        border: 1px solid #D1C4E9; /* 柔和的紫色边框 */
        border-radius: 12px; /* 大圆角 */
        margin-top: 1.2em; /* 为标题留出空间 */
        padding: 15px; /* 内部留白 */
        font-weight: bold;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 15px;
        padding: 0 5px;
        color: #673AB7; /* 标题颜色: 深紫 */
        background-color: transparent;
    }

    /* ——— 按钮 ——— */
    QPushButton {
        background-color: #B39DDB; /* 默认浅紫 */
        border: none;
        border-radius: 8px; /* 圆角按钮 */
        color: white; /* 白色文字 */
        padding: 8px 15px;
        font-size: 13px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: #9575CD; /* 悬停加深 */
    }

    QPushButton:pressed {
        background-color: #7E57C2; /* 按下更深 */
        padding-top: 9px; /* 按下效果 */
        padding-bottom: 7px;
    }
    
    /* 特殊按钮：如"应用配置"这种次要按钮，可以给不同颜色 */
    QPushButton#measure_ensure {
        background-color: #CE93D8;
        color: #FFFFFF;
    }
     QPushButton#measure_ensure:hover {
        background-color: #BA68C8;
    }


    /* ——— 输入控件 (下拉框, 数字框) ——— */
    QComboBox, QSpinBox {
        border: 1px solid #D1C4E9;
        border-radius: 6px;
        padding: 6px;
        background-color: #FAFAFA;
        color: #555;
        selection-background-color: #B39DDB; /* 选中项背景 */
    }
    QComboBox:hover, QSpinBox:hover {
        border: 1px solid #B39DDB; /* 悬停高亮边框 */
    }
    QComboBox::drop-down {
        border: none;
        background: transparent;
        width: 20px;
    }
    /* 可以添加自定义下拉箭头图标，这里暂时省略 */


    /* ——— 标签与文本显示 ——— */
    QLabel {
        color: #424242;
        font-size: 13px;
    }
    
    /* 顶部的模式提示信息 Label */
    QLabel#info {
        background-color: rgba(103, 58, 183, 0.15); /* 半透明深紫色背景 */
        border: 1px solid rgba(103, 58, 183, 0.3);
        border-radius: 6px;
        padding: 8px;
        color: #512DA8;
        font-weight: bold;
        font-size: 14px;
    }

    /* 视频显示区域 */
    QLabel#video_label {
        background-color: #000; /* 视频未加载时黑色背景 */
        border: 3px solid rgba(179, 157, 219, 0.5); /* 半透明紫色边框装饰 */
        border-radius: 12px; /* 视频画面也圆角 */
    }

    /* ——— 日志框 ——— */
    QPlainTextEdit {
        background-color: #FFFFFF;
        border: 1px solid #D1C4E9;
        border-radius: 10px;
        padding: 8px;
        color: #555555;
        font-family: Consolas, "Courier New", monospace;
        font-size: 12px;
    }
    
    /* 滚动条美化 (可选，增加细节) */
    QScrollBar:vertical {
        border: none;
        background: #F3E5F5;
        width: 8px;
        margin: 0px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #CE93D8;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background: #BA68C8;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    """