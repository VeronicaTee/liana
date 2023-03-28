use iced::{widget::tooltip, Length};

use crate::{component::text::*, icon, theme, widget::*};

pub struct Badge {
    icon: crate::widget::Text<'static>,
    style: theme::Badge,
}

impl Badge {
    pub fn new(icon: crate::widget::Text<'static>) -> Self {
        Self {
            icon,
            style: theme::Badge::Standard,
        }
    }
    pub fn style(self, style: theme::Badge) -> Self {
        Self {
            icon: self.icon,
            style,
        }
    }
}

impl<'a, Message: 'a> From<Badge> for Element<'a, Message> {
    fn from(badge: Badge) -> Element<'a, Message> {
        Container::new(badge.icon.width(Length::Units(20)))
            .width(Length::Units(40))
            .height(Length::Units(40))
            .style(theme::Container::Badge(badge.style))
            .center_x()
            .center_y()
            .into()
    }
}

pub fn receive<T>() -> Container<'static, T> {
    Container::new(icon::receive_icon().width(Length::Units(20)))
        .width(Length::Units(40))
        .height(Length::Units(40))
        .style(theme::Container::Badge(theme::Badge::Standard))
        .center_x()
        .center_y()
}

pub fn spend<T>() -> Container<'static, T> {
    Container::new(icon::send_icon().width(Length::Units(20)))
        .width(Length::Units(40))
        .height(Length::Units(40))
        .style(theme::Container::Badge(theme::Badge::Standard))
        .center_x()
        .center_y()
}

pub fn coin<T>() -> Container<'static, T> {
    Container::new(icon::coin_icon().width(Length::Units(20)))
        .width(Length::Units(40))
        .height(Length::Units(40))
        .style(theme::Container::Badge(theme::Badge::Standard))
        .center_x()
        .center_y()
}

pub fn unconfirmed<'a, T: 'a>() -> Container<'a, T> {
    Container::new(
        tooltip::Tooltip::new(
            Container::new(text("  Unconfirmed  ").small())
                .padding(3)
                .style(theme::Container::Pill(theme::Pill::Simple)),
            "Do not treat this as a payment until it is confirmed",
            tooltip::Position::Top,
        )
        .style(theme::Container::Card(theme::Card::Simple)),
    )
}

pub fn deprecated<'a, T: 'a>() -> Container<'a, T> {
    Container::new(
        tooltip::Tooltip::new(
            Container::new(text("  Deprecated  ").small())
                .padding(3)
                .style(theme::Container::Pill(theme::Pill::Simple)),
            "This spend cannot be included anymore in the blockchain",
            tooltip::Position::Top,
        )
        .style(theme::Container::Card(theme::Card::Simple)),
    )
}

pub fn spent<'a, T: 'a>() -> Container<'a, T> {
    Container::new(
        tooltip::Tooltip::new(
            Container::new(text("  Spent  ").small())
                .padding(3)
                .style(theme::Container::Pill(theme::Pill::Simple)),
            "The spend transaction was included in the blockchain",
            tooltip::Position::Top,
        )
        .style(theme::Container::Card(theme::Card::Simple)),
    )
}