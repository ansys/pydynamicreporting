from .adr import BaseModel


class Item(BaseModel):

    @property
    def tags(self):
        ...

    def set_tags(self):
        ...

    def get_tags(self):
        ...

    def add_tag(self):
        ...

    # todo: abstract or overrideable
    def set_content(self):
        ...

    def create(self):
        ...

    def save(
            self,
            *args,
    ):
        ...

    def delete(self):
        ...

    def visualize(self):  # or render()
        ...


class String(Item):
    ...


class Text(String):
    ...


class Table(Item):
    ...


class Plot(Table):
    ...


class Tree(Item):
    ...


class Scene(Item):
    ...


class Image(Item):
    ...


class HTML(Item):
    ...


class Animation(Item):
    ...


class File(Item):
    ...


class Session(BaseModel):
    ...


class Dataset(BaseModel):
    ...
