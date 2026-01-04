# component/theme_style.py

class PurpleTheme:
    STYLE_SHEET = """
    QWidget {
        background-color: #F8F7FC; 
        color: #4A4A4A;             
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        outline: none;
    }

    QPushButton {
        background-color: #FFFFFF;
        border: 1px solid #D1C4E9;  
        border-radius: 8px;        
        color: #673AB7;             
        padding: 6px 15px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: #EDE7F6;  
        border: 1px solid #B39DDB;
    }
    QPushButton:pressed {
        background-color: #D1C4E9;  
        padding-top: 7px;          
        padding-left: 16px;
    }

    QLineEdit, QTextEdit, QSpinBox {
        background-color: #FFFFFF;
        border: 2px solid #E1E1E1;
        border-radius: 6px;
        padding: 5px;
        color: #333333;
        selection-background-color: #B39DDB;
        font-size: 14px;
    }
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
        border: 2px solid #9575CD; 
    }

    QListWidget {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 5px;
    }
    QListWidget::item {
        height: 40px;
        border-radius: 4px;
        margin-bottom: 2px;
        padding-left: 5px;
    }
    QListWidget::item:hover {
        background-color: #F3E5F5;
    }
    QListWidget::item:selected {
        background-color: #D1C4E9; 
        color: #311B92;            
        border-left: 4px solid #7E57C2;
    }

    QLabel {
        background-color: transparent; 
        font-size: 14px;
    }
    QLabel#title_label {
        font-size: 18px;
        font-weight: bold;
        color: #512DA8;
    }
    
    QLabel#video_label {
        background-color: #000000;
        border: 3px solid #D1C4E9;
        border-radius: 4px;
    }
    
    QLabel#info_label {
        background-color: #EDE7F6;
        border: 1px solid #D1C4E9;
        border-radius: 6px;
        padding: 10px;
        color: #4527A0;
    }

    QScrollBar:vertical {
        border: none;
        background: #F1F1F1;
        width: 8px;
        margin: 0px 0px 0px 0px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #D1C4E9;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background: #B39DDB;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    """