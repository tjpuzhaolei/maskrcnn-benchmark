from torch import nn

try:
    from torch.hub import load_state_dict_from_url
except ImportError:
    from torch.utils.model_zoo import load_url as load_state_dict_from_url

# from .utils import load_state_dict_from_url


__all__ = ['MobileNetV2', 'mobilenet_v2']

model_urls = {
    'mobilenet_v2': 'https://download.pytorch.org/models/mobilenet_v2-b0353104.pth',
}


class ConvBNReLU(nn.Sequential):
    def __init__(self, in_planes, out_planes, kernel_size=3, stride=1, groups=1):
        padding = (kernel_size - 1) // 2
        super(ConvBNReLU, self).__init__(
            nn.Conv2d(in_planes, out_planes, kernel_size, stride, padding, groups=groups, bias=False),
            nn.BatchNorm2d(out_planes),
            nn.ReLU6(inplace=True)
        )


class InvertedResidual(nn.Module):
    def __init__(self, inp, oup, stride, expand_ratio):
        super(InvertedResidual, self).__init__()
        self.stride = stride
        assert stride in [1, 2]

        hidden_dim = int(round(inp * expand_ratio))
        self.use_res_connect = self.stride == 1 and inp == oup

        layers = []
        if expand_ratio != 1:
            # pw
            layers.append(ConvBNReLU(inp, hidden_dim, kernel_size=1))
        layers.extend([
            # dw
            ConvBNReLU(hidden_dim, hidden_dim, stride=stride, groups=hidden_dim),
            # pw-linear
            nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
            nn.BatchNorm2d(oup),
        ])
        self.conv = nn.Sequential(*layers)

    def forward(self, x):
        if self.use_res_connect:
            return x + self.conv(x)
        else:
            return self.conv(x)


class MobileNetV2(nn.Module):
    def __init__(self, num_classes=1000, width_mult=1.0):
        super(MobileNetV2, self).__init__()
        block = InvertedResidual
        input_channel = 32  # 3*416*416 -> 32*112*112
        last_channel = 1280
        self.return_features = {}
        inverted_residual_setting = [
            # t, c, n, s
            [1, 16, 1, 1],  # 32x112x112 -> 16x112x112
            [6, 24, 2, 2],  # 16x112x112 -> 24x56x56
            [6, 32, 3, 2],  # 24x56x56 -> 32x28x28
            [6, 64, 4, 2],  # 32x28x28 -> 64x14x14
            [6, 96, 3, 1],  # 64x14x14 -> 96x14x14
            [6, 160, 3, 2],  # 96x14x14 -> 160x7x7
            # [6, 320, 1, 1],  # 160x7x7 -> 320x7x7
        ]

        # building first layer
        input_channel = int(input_channel * width_mult)
        # self.last_channel = int(last_channel * max(1.0, width_mult))
        features = [ConvBNReLU(3, input_channel, stride=2)]

        # building inverted residual blocks
        for t, c, n, s in inverted_residual_setting:
            output_channel = int(c * width_mult)
            for i in range(n):
                stride = s if i == 0 else 1
                last_bottleneck_layer = block(input_channel, output_channel, stride, expand_ratio=t)
                features.append(last_bottleneck_layer)
                input_channel = output_channel

            if c == 24:
                self.layer_56 = nn.Sequential(*features)
                features = []
            if c == 32:
                self.layer_28 = nn.Sequential(*features)
                features = []
            if c == 96:
                self.layer_14 = nn.Sequential(*features)
                features = []
            if c == 320:
                self.layer_7 = nn.Sequential(*features)
                features = []

        # building last several layers
        # features.append(ConvBNReLU(input_channel, self.last_channel, kernel_size=1))
        # make it nn.Sequential
        # self.features = nn.Sequential(*features)

        # building classifier
        # self.classifier = nn.Sequential(
        #     nn.Dropout(0.2),
        #     nn.Linear(self.last_channel, num_classes),
        # )

        # weight initialization
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                nn.init.zeros_(m.bias)

    def forward(self, x):
        outputs = []
        x = self.layer_56(x)
        outputs.append(x)
        x = self.layer_28(x)
        outputs.append(x)
        x = self.layer_14(x)
        outputs.append(x)
        x = self.layer_7(x)
        outputs.append(x)
        return outputs

        # x = self.features(x)
        # x = x.mean([2, 3])
        # x = self.classifier(x)
        # return x


def mobilenet_v2(pretrained=False, progress=True, **kwargs):
    """
    Constructs a MobileNetV2 architecture from
    `"MobileNetV2: Inverted Residuals and Linear Bottlenecks" <https://arxiv.org/abs/1801.04381>`_.

    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
        progress (bool): If True, displays a progress bar of the download to stderr
    """
    model = MobileNetV2(**kwargs)
    if pretrained:
        state_dict = load_state_dict_from_url(model_urls['mobilenet_v2'],
                                              progress=progress)
        model.load_state_dict(state_dict)
    return model
