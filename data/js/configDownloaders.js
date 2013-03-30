$(document).ready(function(){

    $.fn.showHideDownloaders = function() {
        $('.downloaderDiv').each(function(){
            var downloaderName = $(this).attr('id');
            var selectedDownloader = $('#editADownloader :selected').val();

            if (selectedDownloader+'Div' == downloaderName)
                $(this).show();
            else
                $(this).hide();

        });
    }

    $.fn.addDownloader = function (id, name, url, key, isDefault, showDownloader) {

        if (url.match('/$') == null)
            url = url + '/'

        var newData = [isDefault, [name, url, key]];
        newznabDownloaders[id] = newData;

        if (!isDefault)
        {
            $('#editANewznabDownloader').addOption(id, name);
            $(this).populateNewznabSection();
        }

        if ($('#downloaderOrderList > #'+id).length == 0 && showDownloader != false) {
            var toAdd = '<li class="ui-state-default" id="'+id+'"> <input type="checkbox" id="enable_'+id+'" class="downloader_enabler" CHECKED> <a href="'+url+'" class="imgLink" target="_new"><img src="'+sbRoot+'/images/downloaders/newznab.gif" alt="'+name+'" width="16" height="16"></a> '+name+'</li>'

            $('#downloaderOrderList').append(toAdd);
            $('#downloaderOrderList').sortable("refresh");
        }

        $(this).makeNewznabDownloaderString();

    }

    $.fn.updateDownloader = function (id, url, key) {

        newznabDownloaders[id][1][1] = url;
        newznabDownloaders[id][1][2] = key;

        $(this).populateNewznabSection();

        $(this).makeNewznabDownloaderString();

    }

    $.fn.deleteDownloader = function (id) {

        $('#editANewznabDownloader').removeOption(id);
        delete newznabDownloaders[id];
        $(this).populateNewznabSection();

        $('#downloaderOrderList > #'+id).remove();

        $(this).makeNewznabDownloaderString();

    }

    $.fn.populateNewznabSection = function() {

        var selectedDownloader = $('#editANewznabDownloader :selected').val();

        if (selectedDownloader == 'addNewznab') {
            var data = ['','',''];
            var isDefault = 0;
            $('#newznab_add_div').show();
            $('#newznab_update_div').hide();
        } else {
            var data = newznabDownloaders[selectedDownloader][1];
            var isDefault = newznabDownloaders[selectedDownloader][0];
            $('#newznab_add_div').hide();
            $('#newznab_update_div').show();
        }

        $('#newznab_name').val(data[0]);
        $('#newznab_url').val(data[1]);
        $('#newznab_key').val(data[2]);

        if (selectedDownloader == 'addNewznab') {
            $('#newznab_name').removeAttr("disabled");
            $('#newznab_url').removeAttr("disabled");
        } else {

            $('#newznab_name').attr("disabled", "disabled");

            if (isDefault) {
                $('#newznab_url').attr("disabled", "disabled");
                $('#newznab_delete').attr("disabled", "disabled");
            } else {
                $('#newznab_url').removeAttr("disabled");
                $('#newznab_delete').removeAttr("disabled");
            }
        }

    }

    $.fn.makeNewznabDownloaderString = function() {

        var provStrings = new Array();

        for (var id in newznabDownloaders) {
            provStrings.push(newznabDownloaders[id][1].join('|'));
        }

        $('#newznab_string').val(provStrings.join('!!!'))

    }

    $.fn.refreshDownloaderList = function() {
            var idArr = $("#downloaderOrderList").sortable('toArray');
            var finalArr = new Array();
            $.each(idArr, function(key, val) {
                    var checked = + $('#enable_'+val).prop('checked') ? '1' : '0';
                    finalArr.push(val + ':' + checked);
            });

            $("#downloader_order").val(finalArr.join(' '));
    }

    var newznabDownloaders = new Array();

    $('.newznab_key').change(function(){

        var downloader_id = $(this).attr('id');
        downloader_id = downloader_id.substring(0, downloader_id.length-'_hash'.length);

        var url = $('#'+downloader_id+'_url').val();
        var key = $(this).val();

        $(this).updateDownloader(downloader_id, url, key);

    });

    $('#newznab_key').change(function(){

        var selectedDownloader = $('#editANewznabDownloader :selected').val();

        var url = $('#newznab_url').val();
        var key = $('#newznab_key').val();

        $(this).updateDownloader(selectedDownloader, url, key);

    });

    $('#editADownloader').change(function(){
        $(this).showHideDownloaders();
    });

    $('#editANewznabDownloader').change(function(){
        $(this).populateNewznabSection();
    });

    $('.downloader_enabler').live('click', function(){
        $(this).refreshDownloaderList();
    });


    $('#newznab_add').click(function(){

        var selectedDownloader = $('#editANewznabDownloader :selected').val();

        var name = $('#newznab_name').val();
        var url = $('#newznab_url').val();
        var key = $('#newznab_key').val();

        var params = { name: name }

        // send to the form with ajax, get a return value
        $.getJSON(sbRoot + '/config/downloaders/canAddNewznabDownloader', params,
            function(data){
                if (data.error != undefined) {
                    alert(data.error);
                    return;
                }

                $(this).addDownloader(data.success, name, url, key, 0);
        });


    });

    $('.newznab_delete').click(function(){

        var selectedDownloader = $('#editANewznabDownloader :selected').val();

        $(this).deleteDownloader(selectedDownloader);

    });

    // initialization stuff

    $(this).showHideDownloaders();

    $("#downloaderOrderList").sortable({
        placeholder: 'ui-state-highlight',
        update: function (event, ui) {
            $(this).refreshDownloaderList();
        }
    });

    $("#downloaderOrderList").disableSelection();

});
