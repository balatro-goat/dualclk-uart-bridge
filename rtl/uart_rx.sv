`timescale 1ns/1ps

module uart_rx #(
    parameter integer RX_TICK_DIV = 2
)(
    input logic clk,
    input logic rst_n,
    input logic rxd,

    output logic [7:0] byte_data,
    output logic byte_valid,
    output logic frame_error
);

    logic rxd_sync;
    logic sample_tick;

    localparam  [2:0]
        S_IDLE = 3'd0,
        S_START = 3'd1,
        S_DATA = 3'd2,
        S_STOP = 3'd3,
        S_RECOVER = 3'd4;
    
    logic [2:0] state;
    logic [2:0] next_state;

    logic [3:0] tick_count;
    logic [2:0] bit_index;
    logic [7:0] shift_reg;

    rxd_sync_2ff u_rxd_sync (
        .clk(clk),
        .rst_n(rst_n),
        .rxd_async(rxd),
        .rxd_sync(rxd_sync)
    );

    tick_gen #(
        .DIV(RX_TICK_DIV)
    ) u_rx_tick_gen (
        .clk(clk),
        .rst_n(rst_n),
        .tick(sample_tick)
    );

    always @(*) begin
        next_state = state;

        case (state)
            S_IDLE: begin
                if(!rxd_sync)
                    next_state = S_START;
            end

            S_START:begin
                if (sample_tick && tick_count == 4'd7) begin
                    if (!rxd_sync)
                        next_state = S_DATA;
                    else
                        next_state = S_IDLE;
                end
            end

            S_DATA: begin
                if (
                    sample_tick &&
                    tick_count == 4'd15 &&
                    bit_index == 3'd7
                )
                    next_state = S_STOP;
            end

            S_STOP: begin
                if (
                    sample_tick &&
                    tick_count == 4'd15
                ) begin
                    if(rxd_sync)
                        next_state = S_IDLE;
                    else
                        next_state = S_RECOVER;
                end    
            end

            S_RECOVER: begin
                if (rxd_sync)
                    next_state = S_IDLE;
            end

            default: begin
                next_state = S_IDLE;
            end
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            tick_count <= 4'd0;
            bit_index <= 3'd0;
            shift_reg <= 8'h00;

            byte_data <= 8'h00;
            byte_valid <= 1'b0;
            frame_error <= 1'b0;
        end
        else begin
            state <= next_state;

            byte_valid <= 1'b0;
            frame_error <= 1'b0;

            case (state)
                S_IDLE: begin
                    tick_count <= 4'd0;
                    bit_index <= 3'd0;
                    shift_reg <= 8'h00;
                end

                S_START: begin
                    if (sample_tick) begin
                        if (tick_count == 4'd7)
                            tick_count <= 4'd0;
                        else
                            tick_count <= tick_count + 1'b1;
                    end
                end

                S_DATA: begin
                    if (sample_tick) begin
                        if (tick_count == 4'd15) begin
                            tick_count <= 4'd0;

                            shift_reg[bit_index] <= rxd_sync;

                            if (bit_index == 3'd7)
                                bit_index <= 3'd0;
                            else
                                bit_index <= bit_index + 3'd1;
                        end
                        else begin
                            tick_count <= tick_count + 1'b1;
                        end
                    end
                end

                S_STOP: begin
                    if (sample_tick) begin
                        if (tick_count == 4'd15) begin
                            tick_count <= 4'd0;

                            if (rxd_sync) begin
                                byte_data <= shift_reg;
                                byte_valid <= 1'b1;
                            end
                            else begin
                                frame_error <= 1'b1;
                            end
                        end
                        else begin
                            tick_count <= tick_count + 1'b1;
                        end
                    end
                end

                S_RECOVER: begin
                    tick_count <= 4'd0;
                    bit_index <= 3'd0;
                    shift_reg <= 8'h00;
                end

                default: begin
                    tick_count <= 4'd0;
                end
            endcase
        end
    end

endmodule