from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput


class Example(App):
    def build(self):
        self.window = GridLayout()
        self.window.cols = 1
        self.window.size_hint = (0.6, 0.7)
        self.window.pos_hint = {"center_x":0.5, "center_y":0.5}

        self.comments = Label(text='Your comments:')
        self.window.add_widget(self.comments)

        self.user = TextInput(multiline=True,
                              padding_y = (20,20)
                              )
        self.window.add_widget(self.user)

        self.button = Button(text="Collect data to pdf and excel",
                             size_hint = (1,0.4),
                             bold = True,
                             background_color = '#00FFCE')
        self.button.bind(on_press=self.printHello)
        self.window.add_widget(self.button)

        return self.window

    def printHello(self, instance):
        self.comments.text = 'Printed'


if __name__ == "__main__":
    Example().run()
