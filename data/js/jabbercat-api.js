var api_object = null;
var account_jid = null;
var messages_parent = document.getElementById("messages");
var messages = new Array();
var avatar_addresses = {};
var message_uid_index = {};
var marker_owner_index = {};

var scroll_to_bottom = function() {
    // delay to ensure that the DOM has updated already
    setTimeout(
        function(){
            window.scrollTo(0, document.body.scrollHeight);
        },
        50
    );
}

var insertAfter = function(parent, node_to_insert, target) {
    if (target === null) {
        parent.insertBefore(node_to_insert, parent.firstChild);
        return false;
    } else {
        var next_sibling = target.nextSibling;
        if (next_sibling === null) {
            parent.appendChild(node_to_insert);
            return true;
        } else {
            parent.insertBefore(node_to_insert, next_sibling);
            return false;
        }
    }
}

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

var create_avatar_img = function(from_jid, display_name) {
    var img_el = document.createElement("img");
    img_el.src = autoget_avatar_address(from_jid, display_name);
    return img_el;
}

var make_message_container = function() {
    var messages_el = document.createElement("div");
    messages_el.classList.add("message-block-messages");
    return messages_el;
}

var make_clearfix = function() {
    var clearfix = document.createElement("div");
    clearfix.classList.add("clearfix");
    return clearfix;
}

var make_message_block = function(first_message) {
    var block_el = document.createElement("div");
    block_el.classList.add("message-block");
    block_el.dataset.from_jid = first_message.dataset.from_jid;
    block_el.dataset.from_self = first_message.dataset.from_self;
    block_el.dataset.display_name = first_message.dataset.display_name;
    block_el.style.background = first_message.dataset.color_weak;
    block_el.dataset.element_type = "message-block";
    if (block_el.dataset.from_self == "true") {
        block_el.classList.add("from-self");
    }

    var avatar_el = document.createElement("div");
    avatar_el.classList.add("avatar");
    avatar_el.appendChild(create_avatar_img(
        first_message.dataset.from_jid,
        first_message.dataset.display_name
    ));
    block_el.appendChild(avatar_el);

    var from_el = document.createElement("div");
    from_el.classList.add("from");
    from_el.style.color = first_message.dataset.color_full;
    from_el.textContent = first_message.dataset.display_name;
    block_el.appendChild(from_el);

    var messages_el = make_message_container();
    messages_el.appendChild(first_message);
    block_el.appendChild(messages_el);

    block_el.appendChild(make_clearfix());
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

var toplevel_get_next = function(toplevel) {
    return toplevel.nextSibling;
}

var toplevel_get_prev = function(toplevel) {
    return toplevel.previousSibling;
}

var toplevel_is_block = function(toplevel) {
    return toplevel.dataset.element_type == "message-block";
}

var toplevel_is_presence_block = function(toplevel) {
    return toplevel.dataset.element_type == "presence-block";
}

var toplevel_to_string = function(toplevel) {
    if (toplevel === null) {
        return "null";
    }
    if (toplevel_is_block(toplevel)) {
        return block_to_string(toplevel);
    }
    return "<toplevel type="+toplevel.dataset.element_type+">";
}

var block_get_next = function(block) {
    var next = block.nextSibling;
    while (next !== null && !toplevel_is_block(next)) {
        next = next.nextSibling;
    }
    return next;
};

var block_get_prev = function(block) {
    var prev = block.previousSibling;
    while (prev !== null && !toplevel_is_block(prev)) {
        prev = prev.previousSibling;
    }
    return prev;
}

var block_to_string = function(block) {
    var first_msg = block_get_first_message(block);
    var first_uid = first_msg && first_msg.dataset.message_uid;
    return "<block from_jid=\""+block.dataset.from_jid+"\" first_uid=\""+first_uid+"\">";
}

var message_get_next_in_block = function(msg) {
    return msg.nextSibling;
};

var message_get_prev_in_block = function(msg) {
    return msg.previousSibling;
};

var message_get_next = function(msg) {
    var next_msg = message_get_next_in_block(msg);
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
    var prev_msg = message_get_prev_in_block(msg);
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
        prev_msg.dataset.from_jid == message_item.dataset.from_jid &&
        (toplevel_get_next(message_get_block(prev_msg)) === null ||
         toplevel_is_block(toplevel_get_next(message_get_block(prev_msg)))))
    {
        var prev_block = message_get_block(prev_msg);
        block_append_message(prev_block, message_item);
    } else if (
        next_msg !== null &&
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

var update_timestamp_at = function(message) {
    var prev_ts;
    var prev = message_get_prev(message);
    if (prev !== null) {
        prev_ts = date_parse(prev.dataset.timestamp);
    } else {
        console.log("prev is null");
    }
    var message_ts = date_parse(message.dataset.timestamp);
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
}

var update_timestamps = function(start_at) {
    console.log("updating timestamps starting at "+start_at);
    update_timestamp_at(start_at);
    var next = message_get_next(start_at);
    if (next !== null) {
        update_timestamp_at(next);
    }
    /* var message = start_at;
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
    } */
};

var resize_frame = function(frame_wrap_el) {
    var width = frame_wrap_el.clientWidth;
    var height = width / 16 * 9;
    frame_wrap_el.style.height = height + "px";
};

var add_frame_attachment = function(message_item, frame) {
    var frame_wrap_el = document.createElement("div");
    frame_wrap_el.classList.add("frame-wrapper");

    var iframe_el = document.createElement("iframe");
    iframe_el.src = frame.url;
    frame_wrap_el.appendChild(iframe_el);

    // FIXME: use ResizeObserver here once it’s available
    // cf. https://stackoverflow.com/questions/6492683/

    message_item.children[1].appendChild(frame_wrap_el);

    return function() {
        console.log("post-insert resize!");
        resize_frame(frame_wrap_el);
    };
};

var add_image_attachment = function(message_item, image) {
    var img_el = document.createElement("img");
    img_el.classList.add("attachment");
    img_el.src = image.url;

    message_item.children[1].appendChild(img_el);

    return null;
};

var add_attachment = function(message_item, attachment) {
    var type = attachment.type;
    if (type === "frame") {
        return add_frame_attachment(message_item, attachment.frame);
    } else if (type === "image") {
        return add_image_attachment(message_item, attachment.image);
    } else {
        console.log("unsupported attachment type: "+type);
    }
    return null;
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
    message_item.dataset.message_uid = info.message_uid;

    var timestamp_el = document.createElement("div");
    timestamp_el.classList.add("timestamp");
    timestamp_el.textContent = info.timestamp;
    message_item.appendChild(timestamp_el);

    var body_el = document.createElement("div");
    body_el.innerHTML = info.body;

    var body_wrap_el = document.createElement("div");
    body_wrap_el.classList.add("body");
    body_wrap_el.appendChild(body_el);
    message_item.appendChild(body_wrap_el);

    message_uid_index[info.message_uid] = message_item;

    post_insert_callbacks = new Array();

    for (var i = 0; i < info.attachments.length; ++i) {
        var attachment = info.attachments[i];
        var cb = add_attachment(message_item, attachment);
        if (cb !== null) {
            post_insert_callbacks.push(cb);
        }
    }

    insert_message_item(message_item);

    for (var i = 0; i < post_insert_callbacks.length; ++i) {
        var cb = post_insert_callbacks[i];
        cb();
    }

    scroll_to_bottom();
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

var handle_resize = function(event) {
    var frames = document.getElementsByClassName("frame-wrapper");
    for (var i = 0; i < frames.length; ++i) {
        var frame = frames[i];
        resize_frame(frame);
    }
}

var make_marker = function(event) {
    var marker_el = document.createElement("div");
    marker_el.classList.add("marker");
    marker_el.appendChild(create_avatar_img(event.from_jid, event.display_name));

    var text_el = document.createElement("span");
    // FIXME: l10n/i18n
    text_el.innerText = event.display_name + " has read up to here.";
    marker_el.appendChild(text_el);

    return marker_el;
}

var block_split_at = function(message_item) {
    var block = message_get_block(message_item);
    console.log("request to split block "+block);
    var next_message_in_block = message_get_next_in_block(message_item);
    if (next_message_in_block === null) {
        console.log("no next message -> no-op");
        // this is already the last message; split is a no-op
        // returning block, because the contract is that we return the block
        // containing the pointed-at message
        return block;
    }

    var new_block = block.cloneNode(false);
    // copy over the header
    var msg_container = block_get_messages_container(block);
    var child = block.firstChild;
    while (child !== null && child !== msg_container) {
        new_block.appendChild(child.cloneNode(true));
        child = child.nextSibling;
    }

    var messages_el = make_message_container();
    new_block.appendChild(messages_el);
    var child = next_message_in_block;
    while (child !== null) {
        var next = message_get_next_in_block(child);
        messages_el.appendChild(child);
        child = next;
    }

    new_block.appendChild(make_clearfix());

    insertAfter(block.parentNode, new_block, block);

    return block;
}

/**
 * Try to join the block to the previous one.
 *
 * This is only done if the from_jid is equal, and there are no markers
 * inbetween.
 */
var block_try_join = function(block) {
    var prev = toplevel_get_prev(block);
    if (prev === null || !toplevel_is_block(prev)) {
        console.log(
            "block_try_join: prev is not a block (prev=" +
            toplevel_to_string(prev) + ")");
        return null;
    }

    if (prev.dataset.from_jid !== block.dataset.from_jid) {
        console.log(
            "block_try_join: won’t join blocks with different from_jid"
        );
        return null;
    }

    var my_container = block_get_messages_container(block);
    var their_container = block_get_messages_container(prev);

    var msg = my_container.firstChild;
    while (msg !== null) {
        var next = msg.nextSibling;
        their_container.appendChild(msg);
        update_timestamp_at(msg);
        msg = next;
    }

    block.parentNode.removeChild(block);

    return prev;
}

var put_marker = function(event) {
    console.log("marker for uid "+event.marked_message_uid+" from "+
                event.from_jid);

    var message_item = message_uid_index[event.marked_message_uid];
    if (message_item === undefined) {
        console.log("marker for unknown uid "+event.marked_message_uid);
    }

    var marker = marker_owner_index[event.from_jid];
    if (marker === undefined) {
        marker = make_marker(event);
        marker_owner_index[event.from_jid] = marker;
    }

    var block = message_get_block(message_item);
    var after_block = block_split_at(message_item);
    var former_next_toplevel = toplevel_get_next(marker);

    console.log("block for marked message: "+block);

    if (insertAfter(after_block.parentNode, marker, after_block)) {
        scroll_to_bottom();
    }

    if (former_next_toplevel !== null &&
            toplevel_is_block(former_next_toplevel))
    {
        console.log("former next is block: "+block_to_string(former_next_toplevel));
        block_try_join(former_next_toplevel);
    }

    var next_block = block_get_next(after_block);
    if (next_block !== null) {
        update_timestamp_at(block_get_first_message(next_block));
    }
}

var set_font_family = function(new_family) {
    document.body.style.fontFamily =
        "\""+new_family+"\", \"Noto Color Emoji\"";
}

var make_presence_item = function(event, is_join) {
    var presence_el = document.createElement("div");
    presence_el.classList.add("presence");
    presence_el.dataset.from_jid = event.from_jid;
    presence_el.dataset.display_name = event.display_name;
    presence_el.dataset.timestamp = event.timestamp;
    if (is_join) {
        presence_el.dataset.is_join = "is_join";
        presence_el.classList.add("join");
    } else {
        presence_el.classList.add("part");
    }
    presence_el.appendChild(create_avatar_img(
        event.from_jid,
        event.display_name
    ));

    // FIXME: i18n
    var text_el = document.createElement("span");
    text_el.innerText =
        event.display_name + (is_join ? " has joined." : " has left.");
    presence_el.appendChild(text_el);

    return presence_el;
}

var remove_presence_item = function(presence_item) {
    var block = presence_item.parentNode;
    block.removeChild(presence_item);
    if (block.firstChild === null) {
        block.parentNode.removeChild(block);
    }
}

var join = function(event) {
    // FIXME: should probably insert based on timestamp instead of blind
    // appending

    var presence_block_el = messages_parent.lastChild;
    if (presence_block_el === null ||
            !toplevel_is_presence_block(presence_block_el))
    {
        var presence_block_el = document.createElement("div");
        presence_block_el.dataset.element_type = "presence-block";
        presence_block_el.classList.add("presence-block");
    }

    var child = presence_block_el.lastChild;
    while (child !== null && child.dataset.from_jid !== event.from_jid) {
        child = child.previousSibling;
    }
    if (child !== null && !child.dataset.is_join) {
        // annihilate
        remove_presence_item(child);
        return;
    }

    var presence_el = make_presence_item(event, true);
    presence_block_el.appendChild(presence_el);

    messages_parent.appendChild(presence_block_el);

    scroll_to_bottom();
}

var part = function(event) {
    // FIXME: should probably insert based on timestamp instead of blind
    // appending

    var presence_block_el = messages_parent.lastChild;
    if (presence_block_el === null ||
            !toplevel_is_presence_block(presence_block_el))
    {
        var presence_block_el = document.createElement("div");
        presence_block_el.dataset.element_type = "presence-block";
        presence_block_el.classList.add("presence-block");
    }

    var presence_el = make_presence_item(event, false);
    presence_block_el.appendChild(presence_el);

    messages_parent.appendChild(presence_block_el);

    scroll_to_bottom();
}

var init = function() {
    account_jid = api_object.account_jid;
    window.document.title = api_object.conversation_jid;
    api_object.on_message.connect(add_message);
    api_object.on_avatar_changed.connect(avatar_changed);
    api_object.on_marker.connect(put_marker);
    api_object.on_join.connect(join);
    api_object.on_part.connect(part);
    window.onresize = handle_resize;
    var body = document.body;
    set_font_family(api_object.font_family);
    body.style.fontSize = api_object.font_size;

    api_object.on_font_family_changed.connect(function(new_family){
        console.log("font family changed");
        set_font_family(new_family);
    });

    api_object.on_font_size_changed.connect(function(new_size){
        console.log("font size changed");
        body.style.fontSize = new_size;
    });

    api_object.on_request_html.connect(function() {
        console.log("received HTML request");
        api_object.push_html(body.innerHTML);
    });

    console.log("initialized successfully.");

    api_object.ready();
};

new QWebChannel(qt.webChannelTransport, function (channel) {
    api_object = channel.objects.channel;
    init();
});
