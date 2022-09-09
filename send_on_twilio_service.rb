# source: https://raw.githubusercontent.com/chatwoot/chatwoot/afe31a3156d730955b732fc0c2fdfa5bea040fd4/app/services/twilio/send_on_twilio_service.rb
# docker cp send_on_twilio_service.rb rasachatbot-sidekiq-1:/app/app/services/twilio/send_on_twilio_service.rb

class Twilio::SendOnTwilioService < Base::SendOnChannelService
  private

  def channel_class
    Channel::TwilioSms
  end

  def perform_reply
    begin
      twilio_message = channel.send_message(**message_params)
    rescue Twilio::REST::TwilioError => e
      ChatwootExceptionTracker.new(e, user: message.sender, account: message.account).capture_exception
    end
    message.update!(source_id: twilio_message.sid) if twilio_message
  end

  def message_params
    {
      body: message.content,
      to: contact_inbox.source_id,
      media_url: attachments
    }
  end

  def attachments
    message.attachments.map(&:download_url)
  end

  def inbox
    @inbox ||= message.inbox
  end

  def channel
    @channel ||= inbox.channel
  end

  def outgoing_message?
    message.outgoing? || message.template?
  end
end

