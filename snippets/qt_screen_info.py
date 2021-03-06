"""
Resource list for mucking with DPIs on multiple screens:

- https://stackoverflow.com/questions/42141354/convert-pixel-size-to-point-size-for-fonts-on-multiple-platforms
- https://stackoverflow.com/questions/25761556/qt5-font-rendering-different-on-various-platforms/25929628#25929628
- https://doc.qt.io/qt-5/highdpi.html
- https://stackoverflow.com/questions/20464814/changing-dpi-scaling-size-of-display-make-qt-applications-font-size-get-rendere
- https://stackoverflow.com/a/20465247
- https://doc.qt.io/archives/qt-4.8/qfontmetrics.html#width
- https://forum.qt.io/topic/54136/how-do-i-get-the-qscreen-my-widget-is-on-qapplication-desktop-screen-returns-a-qwidget-and-qobject_cast-qscreen-returns-null/3
- https://forum.qt.io/topic/43625/point-sizes-are-they-reliable/4
- https://stackoverflow.com/questions/16561879/what-is-the-difference-between-logicaldpix-and-physicaldpix-in-qt
- https://doc.qt.io/qt-5/qguiapplication.html#screenAt

"""

from pyqtgraph import QtGui
from PyQt5.QtCore import (
     Qt, QCoreApplication
)

# Proper high DPI scaling is available in Qt >= 5.6.0. This attibute
# must be set before creating the application
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


app = QtGui.QApplication([])
window = QtGui.QMainWindow()
main_widget = QtGui.QWidget()
window.setCentralWidget(main_widget)
window.show()

pxr = main_widget.devicePixelRatioF()

# screen_num = app.desktop().screenNumber()
# screen = app.screens()[screen_num]

screen = app.screenAt(main_widget.geometry().center())

name = screen.name()
size = screen.size()
geo = screen.availableGeometry()
phydpi = screen.physicalDotsPerInch()
logdpi = screen.logicalDotsPerInch()

print(
    # f'screen number: {screen_num}\n',
    f'screen name: {name}\n'
    f'screen size: {size}\n'
    f'screen geometry: {geo}\n\n'
    f'devicePixelRationF(): {pxr}\n'
    f'physical dpi: {phydpi}\n'
    f'logical dpi: {logdpi}\n'
)

print('-'*50)

screen = app.primaryScreen()

name = screen.name()
size = screen.size()
geo = screen.availableGeometry()
phydpi = screen.physicalDotsPerInch()
logdpi = screen.logicalDotsPerInch()

print(
    # f'screen number: {screen_num}\n',
    f'screen name: {name}\n'
    f'screen size: {size}\n'
    f'screen geometry: {geo}\n\n'
    f'devicePixelRationF(): {pxr}\n'
    f'physical dpi: {phydpi}\n'
    f'logical dpi: {logdpi}\n'
)


# app-wide font
font = QtGui.QFont("Hack")
# use pixel size to be cross-resolution compatible?
font.setPixelSize(6)


fm = QtGui.QFontMetrics(font)
fontdpi = fm.fontDpi()
font_h = fm.height()

string = '10000'
str_br = fm.boundingRect(string)
str_w = str_br.width()


print(
    # f'screen number: {screen_num}\n',
    f'font dpi: {fontdpi}\n'
    f'font height: {font_h}\n'
    f'string bounding rect: {str_br}\n'
    f'string width : {str_w}\n'
)
