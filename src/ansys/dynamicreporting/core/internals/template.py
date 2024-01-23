from .adr import BaseModel


class Template(BaseModel):
    def visualize(self):
        ...

    def get_html(self):
        ...

    def render(self):
        ...

    def export(self):
        ...

    def set_filter(self):
        ...

    def set_params(self):
        ...
