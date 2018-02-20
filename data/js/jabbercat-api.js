var api_object = null;
var account_jid = null;
var messages_parent = document.getElementById("messages");
var messages = new Array();
var avatar_addresses = {};

var get_prev_message = function(insertion_timestamp) {
    if (messages.length == 0) {
        return null;
    }
    var prev = null;
    for (var i = 0; i < messages.length; i++) {
        var message = messages[i];
        if (message.dataset.timestamp > insertion_timestamp) {
            return prev;
        }
    }
    return messages[messages.length-1];
};

var autoget_avatar_address = function(address, display_name) {
    var data = avatar_addresses[address];
    if (data === undefined) {
        data = {};
        avatar_addresses[address] = data;
    }

    var url = data[display_name];
    if (url !== undefined) {
        return url;
    }

    var params = new URLSearchParams();
    params.set("peer", address);
    params.set("nick", display_name);
    params.set("account", account_jid);
    url = "avatar:///?" + params.toString() + "#";
    data[display_name] = url;

    return url;
};

var inc_avatar_epoch = function(address) {
    var data = avatar_addresses[address];
    if (data === undefined) {
        return false;
    }

    for (var key in data) {
        if (data.hasOwnProperty(key)) {
            data[key] = data[key] + "x";
        }
    }

    return true;
};

var make_message_block = function(first_message) {
    var block_el = document.createElement("div");
    block_el.classList.add("message-block");
    block_el.dataset.from_jid = first_message.dataset.from_jid;
    block_el.dataset.from_self = first_message.dataset.from_self;
    block_el.dataset.display_name = first_message.dataset.display_name;
    block_el.style.background = first_message.dataset.color_weak;
    if (block_el.dataset.from_self == "true") {
        block_el.classList.add("from-self");
    }

    var avatar_el = document.createElement("div");
    avatar_el.classList.add("avatar");

    var img_el = document.createElement("img");
    img_el.src = autoget_avatar_address(
        first_message.dataset.from_jid,
        first_message.dataset.display_name
    );
    avatar_el.appendChild(img_el);
    block_el.appendChild(avatar_el);

    var from_el = document.createElement("div");
    from_el.classList.add("from");
    from_el.style.color = first_message.dataset.color_full;
    from_el.textContent = first_message.dataset.display_name;
    block_el.appendChild(from_el);

    var messages_el = document.createElement("div");
    messages_el.classList.add("message-block-messages");
    messages_el.appendChild(first_message);
    block_el.appendChild(messages_el);

    var clearfix = document.createElement("div");
    clearfix.classList.add("clearfix");
    block_el.appendChild(clearfix);
    return block_el;
};

var message_get_block = function(msg) {
    return msg.parentNode.parentNode;
};

var block_get_messages_container = function(block) {
    return block.children[2];
};

var block_get_first_message = function(block) {
    var messages_el = block_get_messages_container(block);
    if (messages_el.children.length === 0) {
        return null;
    }
    return messages_el.children[0];
};

var block_get_last_message = function(block) {
    var messages_el = block_get_messages_container(block);
    if (messages_el.children.length === 0) {
        return null;
    }
    return messages_el.children[messages_el.children.length - 1];
};

var block_get_next = function(block) {
    return block.nextSibling;
};

var block_get_prev = function(block) {
    return block.previousSibling;
}

var message_get_next = function(msg) {
    var next_msg = msg.nextSibling;
    if (next_msg !== null) {
        return next_msg;
    }
    var block = message_get_block(msg);
    var next_block = block_get_next(block);
    if (next_block === null) {
        return null;
    }
    var next_msg = block_get_first_message(next_block);
    return next_msg;
};

var message_get_prev = function(msg) {
    console.log("searching for prev of "+msg.dataset.body);
    var prev_msg = msg.previousSibling;
    if (prev_msg !== null && prev_msg.classList.contains("message")) {
        return prev_msg;
    }
    var block = message_get_block(msg);
    var prev_block = block_get_prev(block);
    if (prev_block === null) {
        return null;
    }
    var prev_msg = block_get_last_message(prev_block);
    return prev_msg;
};

var message_get_timestamp_el = function(msg) {
    return msg.children[0];
};

var block_append_message = function(block, msg) {
    var messages_el = block_get_messages_container(block);
    messages_el.appendChild(msg);
};

var block_prepend_message = function(block, msg) {
    var messages_el = block_get_messages_container(block);
    if (messages_el.children.length === 0) {
        messages_el.appendChild(msg);
    } else {
        messages_el.insertBefore(msg, messages_el.children[0]);
    }
};

var insert_message_item = function(message_item) {
    var prev_msg = get_prev_message(message_item.dataset.timestamp);
    var next_msg = null;
    if (prev_msg === null) {
        if (messages.length > 0) {
            next_msg = messages[0];
        }
    } else {
        next_msg = message_get_next(prev_msg);
    }

    if (prev_msg !== null &&
        prev_msg.dataset.from_jid == message_item.dataset.from_jid)
    {
        var prev_block = message_get_block(prev_msg);
        block_append_message(prev_block, message_item);
    } else if (next_msg !== null &&
        next_msg.dataset.from_jid == message_item.dataset.from_jid)
    {
        var next_block = message_get_block(next_msg);
        block_prepend_message(next_block, message_item);
    } else {
        // neither works, need to insert new block
        var block = make_message_block(message_item);
        if (next_msg !== null) {
            var next_block = message_get_block(next_msg);
            next_block.parentNode.insertBefore(block, next_block);
        } else {
            messages_parent.appendChild(block);
        }
    }

    if (prev_msg === null) {
        index = 0;
    } else {
        index = messages.indexOf(prev_msg) + 1;
    }
    messages.splice(index, 0, message_item);

    update_timestamps(message_item);
}

var date_same_day = function(d1, d2) {
    return (
        d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate()  // getDate returns day of month
    );
};

var date_same_hour = function(d1, d2) {
    return (
        date_same_day(d1, d2) &&
        d1.getHours() == d2.getHours()
    );
};

var date_same_minute = function(d1, d2) {
    return (
        date_same_hour(d1, d2) &&
        d1.getMinutes() == d2.getMinutes()
    );
};

var date_same_second = function(d1, d2) {
    return (
        date_same_hour(d1, d2) &&
        d1.getSeconds() == d2.getSeconds()
    );
};

var date_parse = function(s) {
    return new Date(Date.parse(s));
};

var update_timestamps = function(start_at) {
    console.log("updating timestamps starting at "+start_at);
    var message = start_at;
    var message_ts, prev_ts;
    var prev = message_get_prev(message);
    if (prev !== null) {
        prev_ts = date_parse(prev.dataset.timestamp);
    } else {
        console.log("prev is null");
    }
    while (message !== null) {
        message_ts = date_parse(message.dataset.timestamp);
        var ts_el = message_get_timestamp_el(message);
        console.log("looking at "+message_ts+" and prev_ts="+prev_ts);

        if (prev === null || !date_same_day(prev_ts, message_ts)) {
            // full timestamp
            ts_el.textContent = message_ts.toLocaleString().replace(" ", " ");
        } else {
            var prev_block = message_get_block(prev);
            var block = message_get_block(message);
            var time_string = message_ts.toTimeString().slice(0, 8);
            var shown = "", hidden = "";
            if (prev_block !== block) {
                shown = time_string;
            } else if (date_same_minute(prev_ts, message_ts)) {
                hidden = time_string.slice(0, 5);
                shown = time_string.slice(5);
            } else if (date_same_hour(prev_ts, message_ts)) {
                hidden = time_string.slice(0, 2);
                shown = time_string.slice(2);
            } else {
                shown = time_string;
            }

            ts_el.textContent = "";

            var el = document.createElement("span");
            el.classList.add("visual-hidden");
            el.textContent = hidden;
            ts_el.appendChild(el);

            var el = document.createElement("span");
            el.textContent = shown;
            ts_el.appendChild(el);
        }

        prev = message;
        prev_ts = message_ts;
        message = message_get_next(message);
    }
};

var add_message = function(info) {
    var message_item = document.createElement("div");
    message_item.classList.add("message");
    message_item.dataset.timestamp = info.timestamp;
    message_item.dataset.from_jid = info.from_jid;
    message_item.dataset.from_self = info.from_self;
    message_item.dataset.display_name = info.display_name;
    message_item.dataset.color_full = info.color_full;
    message_item.dataset.color_weak = info.color_weak;

    var timestamp_el = document.createElement("div");
    timestamp_el.classList.add("timestamp");
    timestamp_el.textContent = info.timestamp;
    message_item.appendChild(timestamp_el);

    var body_el = document.createElement("div");
    body_el.classList.add("body");
    body_el.innerHTML = info.body;
    message_item.appendChild(body_el);

    insert_message_item(message_item);

    // delay to ensure that the DOM has updated already
    setTimeout(
        function(){window.scrollTo(0, document.body.scrollHeight);},
        50
    );
}

var avatar_changed = function(info) {
    var address = info.address;
    if (!inc_avatar_epoch(address)) {
        console.log("avatars for "+address+" are not on this page!");
        return;
    }

    console.log("avatar changed for "+address);
    var avatars = document.getElementsByClassName("avatar");
    for (var i = 0; i < avatars.length; i++) {
        var avatar = avatars[i];
        var block = avatar.parentNode;
        var avatar_address = block.dataset.from_jid;
        if (avatar_address !== address) {
            console.log("mismatch: "+address+" !== "+avatar_address);
            continue;
        }

        console.log("match!");
        var display_name = block.dataset.display_name;
        var img = avatar.children[0];
        img.src = autoget_avatar_address(address, display_name);
    }

}

var init = function() {
    account_jid = api_object.account_jid;
    api_object.on_message.connect(add_message);
    api_object.on_avatar_changed.connect(avatar_changed);
    var body = document.body;
    body.style.fontFamily = api_object.font_family;
    body.style.fontSize = api_object.font_size;

    api_object.on_font_family_changed.connect(function(new_family){
        console.log("font family changed");
        body.style.fontFamily = new_family;
    });

    api_object.on_font_size_changed.connect(function(new_size){
        console.log("font size changed");
        body.style.fontSize = new_size;
    });

    api_object.ready();
};

new QWebChannel(qt.webChannelTransport, function (channel) {
    api_object = channel.objects.channel;
    init();
});
